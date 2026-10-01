import { Link } from "react-router";
import { t, type MessageKey } from "../i18n/messages.ts";

const actionClass =
  "inline-flex min-h-11 items-center justify-center rounded-md bg-brand px-5 text-base font-medium text-on-brand focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

export function HomePage() {
  return (
    <section aria-labelledby="home-title" className="space-y-3">
      <h1 id="home-title" className="text-2xl font-semibold">
        {t("home.title")}
      </h1>
      <p className="text-base text-ink-muted">{t("home.body")}</p>
    </section>
  );
}

function MessagePage({
  titleKey,
  bodyKey,
  actionKey,
}: {
  titleKey: MessageKey;
  bodyKey: MessageKey;
  actionKey: MessageKey;
}) {
  return (
    <section aria-labelledby="message-title" className="space-y-4">
      <h1 id="message-title" className="text-2xl font-semibold">
        {t(titleKey)}
      </h1>
      <p className="text-base text-ink-muted">{t(bodyKey)}</p>
      <Link to="/" className={actionClass}>
        {t(actionKey)}
      </Link>
    </section>
  );
}

export function NotFoundPage() {
  return (
    <MessagePage titleKey="notFound.title" bodyKey="notFound.body" actionKey="notFound.action" />
  );
}

/** Shown when a route throws while rendering. Never shows error details to the user. */
export function RouteErrorPage() {
  return (
    <div role="alert" className="mx-auto max-w-screen-md p-4">
      <MessagePage
        titleKey="routeError.title"
        bodyKey="routeError.body"
        actionKey="routeError.action"
      />
    </div>
  );
}
