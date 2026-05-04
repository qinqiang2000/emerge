import "@testing-library/jest-dom";

const createMemoryStorage = (): Storage => {
  const store = new Map<string, string>();
  return {
    get length() {
      return store.size;
    },
    clear() {
      store.clear();
    },
    getItem(key: string) {
      return store.get(key) ?? null;
    },
    key(index: number) {
      return Array.from(store.keys())[index] ?? null;
    },
    removeItem(key: string) {
      store.delete(key);
    },
    setItem(key: string, value: string) {
      store.set(key, value);
    },
  };
};

const localStorageMock = createMemoryStorage();

Object.defineProperty(window, "localStorage", {
  configurable: true,
  value: localStorageMock,
});
Object.defineProperty(globalThis, "localStorage", {
  configurable: true,
  value: localStorageMock,
});

await import("@/i18n");
