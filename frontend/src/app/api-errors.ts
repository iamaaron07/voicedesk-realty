export function apiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof TypeError) {
    return "The VoiceDesk API could not be reached. Check your connection and try again.";
  }
  if (error instanceof SyntaxError) {
    return "The VoiceDesk API returned an unexpected response. Please try again shortly.";
  }
  return error instanceof Error && error.message ? error.message : fallback;
}
