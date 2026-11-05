export async function createOrder(): Promise<string> {
  const response = await fetch("/api/orders", { method: "POST" });
  return response.text();
}
