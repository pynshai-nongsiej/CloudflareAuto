export function extractCode(text) {
  // Context is required: do not mistake a date or arbitrary number for an OTP.
  const patterns = [
    /(?:OTP|verification code|security code|one[- ]time (?:password|code)|sign[- ]in code)\b[^\d\n]{0,70}\s*\b(\d{4,8})\b/i,
    /\b(\d{4,8})\b\s*(?:is your|is the)\s*(?:OTP|verification code|security code|code)/i,
  ];
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match) return match[1];
  }
  return null;
}
