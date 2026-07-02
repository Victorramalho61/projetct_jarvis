import { lazy, type ComponentType } from "react";

const RELOAD_FLAG = "jarvis:chunk-reload";

/**
 * Wrapper de React.lazy que recarrega a página uma única vez se o chunk
 * falhar (hash antigo removido do servidor após deploy do frontend).
 * Evita loop infinito via sessionStorage.
 */
export function lazyWithReload<T extends ComponentType<any>>(
  factory: () => Promise<{ default: T }>
) {
  return lazy(async () => {
    try {
      const module = await factory();
      sessionStorage.removeItem(RELOAD_FLAG);
      return module;
    } catch (error) {
      if (!sessionStorage.getItem(RELOAD_FLAG)) {
        sessionStorage.setItem(RELOAD_FLAG, "1");
        window.location.reload();
        return new Promise<{ default: T }>(() => {});
      }
      throw error;
    }
  });
}
