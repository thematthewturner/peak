/** An API failure that carries the HTTP status. */
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

/** Send the student to sign-in. */
export function goToLogin(): void {
  location.replace("/");
}
