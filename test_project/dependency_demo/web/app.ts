import { titleCase } from "./utils/format";

export function formatMessage(msg: string): string {
  return titleCase(msg);
}