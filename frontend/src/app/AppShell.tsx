import { Link, Outlet } from "react-router";
import { t } from "../i18n/messages.ts";

export const MAIN_CONTENT_ID = "main-content";

/**
 * Placeholder mobile shell (designed at 360px first). Header on top, content below,
 * padded for device safe areas so nothing sits under a notch or home indicator when
 * installed. Navigation, session and restaurant context arrive with 0008.
 */
export function AppShell() {
  return (
    <div className="flex min-h-dvh flex-col bg-surface text-ink">
      <a
        href={`#${MAIN_CONTENT_ID}`}
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-10 focus:inline-flex focus:min-h-11 focus:items-center focus:rounded-md focus:bg-brand focus:px-4 focus:text-on-brand"
      >
        {t("app.skipToContent")}
      </a>
      <header className="sticky top-0 border-b border-line bg-brand pt-[env(safe-area-inset-top)] text-on-brand">
        <div className="mx-auto flex min-h-14 max-w-screen-md items-center pl-[max(1rem,env(safe-area-inset-left))] pr-[max(1rem,env(safe-area-inset-right))]">
          <Link
            to="/"
            className="inline-flex min-h-11 min-w-11 items-center text-lg font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-on-brand"
          >
            {t("app.name")}
          </Link>
        </div>
      </header>
      <main
        id={MAIN_CONTENT_ID}
        tabIndex={-1}
        className="mx-auto w-full max-w-screen-md flex-1 pt-6 pb-[max(1.5rem,env(safe-area-inset-bottom))] pl-[max(1rem,env(safe-area-inset-left))] pr-[max(1rem,env(safe-area-inset-right))] focus:outline-none"
      >
        <Outlet />
      </main>
    </div>
  );
}
