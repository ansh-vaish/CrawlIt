export function getBaseUrl() {
  return typeof window === "undefined"
    ? process.env.BACKEND_URL!
    : process.env.NEXT_PUBLIC_BACKEND_URL!;
}
