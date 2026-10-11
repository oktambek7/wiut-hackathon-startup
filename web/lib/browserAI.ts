/* Multilingual E5 running in the visitor's browser (transformers.js + ONNX Runtime Web) inside a Web Worker,
   so the page stays responsive. Same model family as the offline app (intfloat/multilingual-e5-small,
   ONNX export by Xenova, 8-bit). The document text never goes to an AI service: only passage ranks reach our API. */

export const MODEL_ID = "Xenova/multilingual-e5-small";
const MODEL_REVISION = "761b726dd34fb83930e26aab4e9ac3899aa1fa78";
const LIBRARY = "https://cdn.jsdelivr.net/npm/@huggingface/transformers@4.3.0/dist/transformers.min.js";
const TOP_K = 40;
const BATCH = 8;

export type AIProgress = { phase: "download"; loaded: number; total: number } | { phase: "embed"; done: number; total: number };

const WORKER_SOURCE = `
import { pipeline, env } from "${LIBRARY}";
env.allowLocalModels = false;
let extractor = null;
const files = {};
self.onmessage = async (event) => {
  const { id, texts } = event.data;
  try {
    if (!extractor) {
      extractor = await pipeline("feature-extraction", "${MODEL_ID}", {
        dtype: "q8", revision: "${MODEL_REVISION}",
        progress_callback: (p) => {
          if (p.status === "progress" && p.file) {
            files[p.file] = [p.loaded || 0, p.total || 0];
            const all = Object.values(files);
            self.postMessage({ type: "download", loaded: all.reduce((s, f) => s + f[0], 0), total: all.reduce((s, f) => s + f[1], 0) });
          }
        },
      });
    }
    const out = texts.length ? (await extractor(texts, { pooling: "mean", normalize: true })).tolist() : [];
    self.postMessage({ type: "result", id, vectors: out });
  } catch (error) {
    extractor = null;
    self.postMessage({ type: "error", id, message: String(error) });
  }
};`;

let worker: Worker | null = null;
let nextId = 0;
const pending = new Map<number, { resolve: (v: number[][]) => void; reject: (e: Error) => void }>();
let onDownload: ((p: AIProgress) => void) | undefined;

function getWorker(): Worker {
  if (!worker) {
    worker = new Worker(URL.createObjectURL(new Blob([WORKER_SOURCE], { type: "text/javascript" })), { type: "module" });
    worker.onmessage = (e: MessageEvent) => {
      const msg = e.data;
      if (msg.type === "download") return onDownload?.({ phase: "download", loaded: msg.loaded, total: msg.total });
      const job = pending.get(msg.id);
      if (!job) return;
      pending.delete(msg.id);
      if (msg.type === "result") job.resolve(msg.vectors);
      else job.reject(new Error(msg.message));
    };
    worker.onerror = (e) => {
      pending.forEach((job) => job.reject(new Error(e.message || "AI worker failed")));
      pending.clear();
      worker?.terminate();
      worker = null;
    };
  }
  return worker;
}

function embedBatch(texts: string[]): Promise<number[][]> {
  const id = nextId++;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    getWorker().postMessage({ id, texts });
  });
}

async function embed(texts: string[], onDone?: (n: number) => void): Promise<number[][]> {
  const out: number[][] = [];
  for (let i = 0; i < texts.length; i += BATCH) {
    out.push(...(await embedBatch(texts.slice(i, i + BATCH))));
    onDone?.(Math.min(i + BATCH, texts.length));
  }
  return out;
}

const dot = (a: number[], b: number[]) => a.reduce((s, v, i) => s + v * b[i], 0);

/** For each rule: passage ids ordered by the best cosine similarity to any of the rule's queries. */
export async function rankPassages(passages: { id: string; text: string }[], queries: Record<string, string[]>,
                                   onProgress?: (p: AIProgress) => void): Promise<{ ranking: Record<string, string[]>; seconds: number }> {
  const started = performance.now();
  onDownload = onProgress;
  await embedBatch([]); // load (or reuse) the model first so download progress is shown separately
  const vectors = await embed(passages.map((p) => `passage: ${p.text}`), (done) => onProgress?.({ phase: "embed", done, total: passages.length }));
  const ranking: Record<string, string[]> = {};
  for (const [rule, qs] of Object.entries(queries)) {
    const qv = await embed(qs.map((q) => `query: ${q}`));
    const scored = passages.map((p, i) => ({ id: p.id, s: Math.max(...qv.map((q) => dot(vectors[i], q))) }));
    ranking[rule] = scored.sort((a, b) => b.s - a.s).slice(0, TOP_K).map((x) => x.id);
  }
  return { ranking, seconds: (performance.now() - started) / 1000 };
}
