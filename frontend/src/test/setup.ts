import "@testing-library/jest-dom/vitest";

// Node 22+ ships a built-in `localStorage` global backed by a file; without
// `--localstorage-file` it's present but non-functional (no `.clear()`),
// and it wins over jsdom's simulated storage in this Vitest/Node combination.
// Replace it with a minimal, real in-memory implementation for tests.
class MemoryStorage implements Storage {
  private store = new Map<string, string>();

  get length() {
    return this.store.size;
  }

  clear(): void {
    this.store.clear();
  }

  getItem(key: string): string | null {
    return this.store.has(key) ? this.store.get(key)! : null;
  }

  key(index: number): string | null {
    return Array.from(this.store.keys())[index] ?? null;
  }

  removeItem(key: string): void {
    this.store.delete(key);
  }

  setItem(key: string, value: string): void {
    this.store.set(key, String(value));
  }
}

Object.defineProperty(globalThis, "localStorage", {
  value: new MemoryStorage(),
  configurable: true,
  writable: true,
});
