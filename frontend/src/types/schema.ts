export type FieldType = "string" | "number" | "integer" | "boolean" | "array";

export interface SchemaField {
  name: string;
  type: FieldType;
  required: boolean;
  description: string;
  examples: string[];
  enum: string[] | null;
  child_fields: SchemaField[];
}
