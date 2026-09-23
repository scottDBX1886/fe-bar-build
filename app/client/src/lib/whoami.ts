export interface WhoAmI {
  email: string | null;
  user: string | null;
  genieExecution: 'on_behalf_of_user';
}

export async function fetchWhoAmI(): Promise<WhoAmI> {
  const response = await fetch('/api/whoami');
  if (!response.ok) {
    throw new Error(`Unable to resolve signed-in identity (${response.status})`);
  }
  return response.json() as Promise<WhoAmI>;
}
