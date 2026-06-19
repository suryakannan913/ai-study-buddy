const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface ChatResponse {
  response: string;
  conversation_id: number;
  message_id: number;
}

export interface UploadResponse {
  material_id: number;
  filename: string;
  message: string;
}

export interface Material {
  id: number;
  filename: string;
  created_at: string;
}

function handleError(error: unknown): Error {
  if (error instanceof Error) return error;
  return new Error(String(error));
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // ignore non-JSON error bodies
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function sendChat(
  message: string,
  conversationId: number | null,
): Promise<ChatResponse> {
  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
    }),
  });

  return handleResponse<ChatResponse>(res);
}

export async function uploadPDF(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_URL}/upload`, {
    method: "POST",
    body: formData,
  });

  return handleResponse<UploadResponse>(res);
}

export async function getMaterials(): Promise<Material[]> {
  const res = await fetch(`${API_URL}/materials`);
  return handleResponse<Material[]>(res);
}

export async function deleteMaterial(id: number): Promise<void> {
  const res = await fetch(`${API_URL}/materials/${id}`, {
    method: "DELETE",
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
}
