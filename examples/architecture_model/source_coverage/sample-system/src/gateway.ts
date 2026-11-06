import { allowed } from "./rules";
import { normalize } from "./helpers";

export function authorize(role: string): boolean {
    return allowed(normalize(role));
}
