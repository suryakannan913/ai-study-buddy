"use client";

import { useEffect, useState } from "react";
import { getMaterials, deleteMaterial } from "@/lib/api";

interface Material {
  id: number;
  filename: string;
  created_at: string;
}

interface MaterialsListProps {
  refreshTrigger?: number;
}

export default function MaterialsList({ refreshTrigger }: MaterialsListProps) {
  const [materials, setMaterials] = useState<Material[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadMaterials();
  }, [refreshTrigger]);

  async function loadMaterials() {
    setLoading(true);
    setError(null);
    try {
      const data = await getMaterials();
      setMaterials(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load materials."
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Delete this material?")) return;

    try {
      await deleteMaterial(id);
      setMaterials((m) => m.filter((mat) => mat.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed.");
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-4">
        <div className="size-3 animate-spin rounded-full border-2 border-muted border-t-accent" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-600">
        {error}
      </div>
    );
  }

  if (materials.length === 0) {
    return (
      <div className="text-center py-4">
        <p className="text-xs text-muted">No materials uploaded yet.</p>
        <p className="text-xs text-muted/50 mt-1">
          Upload a PDF to get started with RAG.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {materials.map((material) => (
        <div
          key={material.id}
          className="flex items-start justify-between gap-2 rounded-lg bg-card/50 p-3 text-xs hover:bg-card transition-colors"
        >
          <div className="flex-1 min-w-0">
            <p className="font-medium truncate">{material.filename}</p>
            <p className="text-[11px] text-muted mt-0.5">
              {new Date(material.created_at).toLocaleDateString()}
            </p>
          </div>
          <button
            onClick={() => handleDelete(material.id)}
            className="flex-shrink-0 rounded p-1.5 hover:bg-red-500/10 text-red-600 transition-colors"
            title="Delete"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
