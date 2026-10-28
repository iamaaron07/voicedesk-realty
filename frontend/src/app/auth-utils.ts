export function safeInternalPath(value: string | null): string {
  return value && value.startsWith("/") && !value.startsWith("//") && !value.includes("\\") ? value : "/";
}

export function registrationError(password: string, confirmation: string): string | null {
  if (password !== confirmation) return "Passwords do not match.";
  if (password.length < 10 || !/[A-Za-z]/.test(password) || !/[0-9]/.test(password)) {
    return "Use at least 10 characters, including a letter and a number.";
  }
  return null;
}
