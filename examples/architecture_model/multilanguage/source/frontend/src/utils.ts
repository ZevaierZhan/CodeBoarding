import { invoke } from "@tauri-apps/api/core";

export async function readDocument(path: string): Promise<string> {
  return invoke<string>("read_file", { path });
}

export async function openDocument(): Promise<string> {
  return readDocument("notes.txt");
}

export async function previewDocument(): Promise<string> {
  return readDocument("preview.txt");
}
