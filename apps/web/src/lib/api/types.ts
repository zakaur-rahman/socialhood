import type { components } from "@socialhood/api-client";

type Schemas = components["schemas"];

export type Me = Schemas["Me"];
export type WorkspaceSummary = Schemas["WorkspaceSummary"];
export type Workspace = Schemas["WorkspaceOut"];
export type WorkspacePatch = Schemas["WorkspacePatch"];
export type Overview = Schemas["Overview"];
export type ChecklistStep = Schemas["ChecklistStep"];
export type Role = WorkspaceSummary["role"];
export type Plan = WorkspaceSummary["plan"];
