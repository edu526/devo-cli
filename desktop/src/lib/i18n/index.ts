/**
 * Minimal i18n for the desktop app.
 *
 * English is the default. Spanish strings are provided as a stub so the
 * rest of the app can wire `t("key")` calls and the ConfigPage can
 * offer a language selector without any code churn once translations
 * are filled in.
 *
 * The store is reactive: components can read `$locale` to gate logic
 * that depends on language (date format, sort order, etc.) and call
 * `t(key)` for any user-facing string.
 */

import { derived, writable, type Readable } from "svelte/store";

export type Locale = "en" | "es";

const en: Record<string, string> = {
  "app.title": "Devo Desktop",
  "nav.connections": "Connections",
  "nav.instances": "Instances",
  "nav.databases": "Databases",
  "nav.profiles": "AWS Profiles",
  "nav.hosts": "Hosts",
  "nav.config": "Config",
  "nav.logs": "Logs",
  "common.search": "Search…",
  "common.loading": "Loading…",
  "common.refresh": "Refresh",
  "common.download": "Download",
  "common.cancel": "Cancel",
  "common.save": "Save",
  "common.create": "Create",
  "common.delete": "Delete",
  "common.edit": "Edit",
  "common.add": "Add",
  "common.close": "Close",
  "common.required": "Required",
  "common.optional": "Optional",
  "common.yes": "Yes",
  "common.no": "No",
  "common.error": "Error",
  "common.confirm": "Confirm",
  "common.confirmClearLogs": "Clear the sidecar log file?",
  "common.confirmDelete": 'Delete "{name}"?',
  "common.noResults": 'No results match "{query}".',
  "common.empty": "Nothing here yet.",
  "logs.paused": "▶ Resume",
  "logs.playing": "⏸ Pause",
  "logs.path": "Streaming from ~/.devo/sidecar.log",
  "logs.all": "All",
  "connections.start": "Start",
  "connections.stop": "Stop",
  "connections.restart": "Restart",
  "connections.startAll": "Start All",
  "connections.stopAll": "Stop All",
  "connections.uptime": "Uptime",
  "profiles.refresh": "Refresh",
  "profiles.refreshAll": "Refresh All",
  "profiles.identity": "Identity",
  "profiles.setDefault": "Set Default",
  "profiles.default": "Default",
  "instances.new": "New Instance",
  "instances.edit": "Edit Instance",
  "databases.new": "New Database",
  "databases.edit": "Edit Database",
  "hosts.new": "Add Host",
  "config.title": "Configuration",
  "config.theme": "Theme",
  "config.theme.dark": "Dark",
  "config.theme.light": "Light",
  "config.theme.system": "System",
  "config.language": "Language",
  "config.language.en": "English",
  "config.language.es": "Español",
  "update.available": "Update available",
  "update.install": "Download & Install",
  "update.later": "Later",
  "update.checking": "Checking for updates…",
};

const es: Record<string, string> = {
  // Stub: falls back to English keys for untranslated strings. Add
  // translations here incrementally — `t()` returns the key wrapped
  // in [brackets] when a translation is missing so the gap is
  // obvious in QA.
  "app.title": "Devo Escritorio",
  "nav.connections": "Conexiones",
  "nav.instances": "Instancias",
  "nav.databases": "Bases de datos",
  "nav.profiles": "Perfiles AWS",
  "nav.hosts": "Hosts",
  "nav.config": "Configuración",
  "nav.logs": "Registros",
  "common.search": "Buscar…",
  "common.loading": "Cargando…",
  "common.refresh": "Actualizar",
  "common.cancel": "Cancelar",
  "common.save": "Guardar",
  "common.create": "Crear",
  "common.delete": "Eliminar",
  "common.edit": "Editar",
  "common.add": "Añadir",
  "common.required": "Obligatorio",
  "common.optional": "Opcional",
  "common.error": "Error",
  "common.confirmClearLogs": "¿Borrar el archivo de registros del sidecar?",
  "common.confirmDelete": '¿Eliminar "{name}"?',
  "common.noResults": 'Ningún resultado coincide con "{query}".',
  "common.empty": "Nada aquí todavía.",
  "logs.paused": "▶ Reanudar",
  "logs.playing": "⏸ Pausar",
  "logs.path": "Transmitiendo desde ~/.devo/sidecar.log",
  "connections.start": "Iniciar",
  "connections.stop": "Detener",
  "connections.startAll": "Iniciar todo",
  "connections.stopAll": "Detener todo",
  "connections.uptime": "Tiempo activo",
  "profiles.refreshAll": "Actualizar todo",
  "instances.new": "Nueva instancia",
  "databases.new": "Nueva base de datos",
  "hosts.new": "Añadir host",
};

const DICTS: Record<Locale, Record<string, string>> = { en, es };

function detectInitialLocale(): Locale {
  if (typeof navigator === "undefined") return "en";
  const lang = navigator.language.toLowerCase();
  return lang.startsWith("es") ? "es" : "en";
}

export const locale = writable<Locale>(detectInitialLocale());

/** Read a translation for the given key in the active locale. */
export function tFor(loc: Locale, key: string): string {
  const dict = DICTS[loc];
  if (dict && dict[key]) return dict[key];
  // Fall back to English, then to a marker that surfaces the missing
  // translation in the UI so QA can grep for it.
  if (DICTS.en[key]) return DICTS.en[key];
  return `[${key}]`;
}

/** Reactive translator: re-reads whenever the locale store changes. */
export const t: Readable<(key: string) => string> = derived(locale, ($loc) => {
  return (key: string) => tFor($loc, key);
});
