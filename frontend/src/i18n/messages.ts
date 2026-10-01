/**
 * User-facing message catalog (English only in v1, C6.9).
 *
 * Every user-facing string comes from here so a translation layer can replace this
 * module later without touching components. Keys are dot-separated by area.
 */
export const messages = {
  "app.name": "RMS",
  "app.skipToContent": "Skip to main content",
  "home.title": "Welcome",
  "home.body": "Your restaurant workspace is being set up. Sign-in arrives in a later release.",
  "notFound.title": "Page not found",
  "notFound.body": "This page does not exist or has moved.",
  "notFound.action": "Go to the home screen",
  "routeError.title": "Something went wrong",
  "routeError.body": "This screen could not be shown. Try again, or go back to the home screen.",
  "routeError.action": "Go to the home screen",
  "api.error.network": "You appear to be offline or the server is unreachable. Try again.",
  "api.error.unexpected": "Something went wrong on our side. Try again.",
} as const;

export type MessageKey = keyof typeof messages;

export function t(key: MessageKey): string {
  return messages[key];
}
