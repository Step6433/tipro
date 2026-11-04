// getRandomValues is also available on plain HTTP in a local Wi-Fi network.
// randomUUID requires a secure context and is unavailable on phone → LAN HTTP.
export function createIdempotencyKey() {
  const bytes = new Uint8Array(32)
  globalThis.crypto.getRandomValues(bytes)
  return Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('')
}
