// Browser signals are advisory: Safari does not expose total/free RAM.
export async function deviceSupport() {
  const missing = [];
  if (!isSecureContext || !crypto?.subtle) missing.push('Open the HTTPS link in a current browser.');
  if (typeof Worker === 'undefined' || typeof WebAssembly === 'undefined') missing.push('Local chat needs WebAssembly and web workers.');
  if (typeof indexedDB === 'undefined') missing.push('Enable browser storage for this site.');
  let estimate = {};
  try { estimate = await navigator.storage?.estimate?.() || {}; } catch {}
  const free = Number.isFinite(estimate.quota) && Number.isFinite(estimate.usage) ? Math.max(0, estimate.quota - estimate.usage) : null;
  return {missing, free, memory: navigator.deviceMemory || null};
}

export async function checkDownloadSpace(bytes) {
  const {free} = await deviceSupport();
  if (free !== null && free < bytes + 32 * 1024 * 1024) {
    throw Error('Not enough browser storage for this model. Free at least 270 MB, then try again.');
  }
}
