"use client";

import { X } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { ContactAvatar } from "@/components/inbox/ContactAvatar";
import { LeadStageSection } from "@/components/leads/LeadStageSection";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api/errors";
import {
  useContact,
  useContactFields,
  useCreateTag,
  useRecordConsent,
  useTagContact,
  useTags,
  useUpdateContact,
} from "@/lib/api/queries";
import type { ConsentChannel, ContactConsent, ContactRecord, FieldDefinition } from "@/lib/api/types";
import { buildPatch, editFrom, type ContactEdit } from "@/lib/contacts/edit";
import { PLATFORM_LABEL } from "@/lib/inbox/format";
import { formatDay } from "@/lib/tz";
import { toastError } from "@/lib/toast-error";
import { useCurrentWorkspace } from "@/lib/workspace";
import { EYEBROW } from "@/styles/tokens";

import { ContactTimeline } from "./ContactTimeline";
import { TagChip } from "./TagChip";

const CHANNEL_LABEL: Record<ConsentChannel, string> = { instagram: "Instagram", whatsapp: "WhatsApp", email: "Email" };
const CONSENT_SOURCE: Record<ContactConsent["source"], string> = {
  platform_optin: "Opted in on the platform",
  flow: "Answered in a conversation",
  stop_reply: "Replied STOP",
  member: "Recorded by your team",
  import: "Imported",
};
const NONE = "none";

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby={id} className="space-y-3">
      <h3 id={id} className={EYEBROW}>
        {title}
      </h3>
      {children}
    </section>
  );
}

/**
 * The contact drawer (GR-17): one contact's tags, email, phone and custom fields (editable by any
 * member), the lead stage (any member moves it), marketing consent (admins record it), and a
 * read-only timeline that includes the stage history. A full-screen panel
 * below 768 px and a 420 px panel beside the page from there. It opens from the contacts list and
 * from the inbox's details panel.
 */
export function ContactDrawer({ contactId, onClose }: { contactId: string | null; onClose: () => void }) {
  const { id: wid } = useCurrentWorkspace();
  const contact = useContact(wid, contactId);
  return (
    <Sheet open={contactId !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent size="panel" className="gap-0 overflow-y-auto">
        {contactId !== null && contact.data ? (
          <DrawerBody record={contact.data} />
        ) : (
          <>
            <SheetHeader>
              <SheetTitle>Contact</SheetTitle>
              <SheetDescription className="sr-only">Details, tags and history for this contact.</SheetDescription>
            </SheetHeader>
            <div className="p-4">
              {contact.isError ? (
                <p className="text-sm text-fg-secondary">
                  This contact did not load.{" "}
                  <Button variant="link" size="xs" className="px-0" onClick={() => void contact.refetch()}>
                    Try again
                  </Button>
                </p>
              ) : (
                <div role="status" aria-label="Loading the contact" className="space-y-3">
                  <Skeleton className="size-12 rounded-full" />
                  <Skeleton className="h-3 w-2/3" />
                  <Skeleton className="h-3 w-1/2" />
                </div>
              )}
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}

function DrawerBody({ record }: { record: ContactRecord }) {
  const { id: wid, slug, role, timezone } = useCurrentWorkspace();
  const fields = useContactFields(wid);
  const definitions = fields.data?.items ?? [];
  const admin = role !== "agent";
  // Remount the form when the saved values change, so it starts from them. It waits for the field
  // definitions, which give it its fields.
  const formKey = JSON.stringify([record.email, record.phone, record.fields]);
  return (
    <>
      <SheetHeader className="flex-row items-center gap-3 border-b border-line">
        <ContactAvatar id={record.id} name={record.name} pictureUrl={record.profile_picture_url} platform={record.platform as "instagram" | "whatsapp"} />
        <div className="min-w-0">
          <SheetTitle className="truncate">{record.name}</SheetTitle>
          <SheetDescription className="truncate">
            {[record.username ? `@${record.username}` : null, PLATFORM_LABEL[record.platform as "instagram" | "whatsapp"]]
              .filter(Boolean)
              .join(" · ")}
          </SheetDescription>
          {record.conversation_id ? (
            <Link
              href={`/w/${slug}/inbox/${record.conversation_id}` as Route}
              className="text-sm text-brand-fg underline-offset-4 hover:underline"
            >
              Open conversation
            </Link>
          ) : null}
        </div>
      </SheetHeader>
      <div className="flex flex-col gap-6 p-4">
        <Section id="contact-lead-stage" title="Lead stage">
          <LeadStageSection record={record} />
        </Section>
        <Section id="contact-tags" title="Tags">
          <TagsEditor record={record} admin={admin} />
        </Section>
        <Section id="contact-details" title="Details">
          {fields.isPending ? (
            <Skeleton className="h-40 w-full" aria-label="Loading the contact's details" />
          ) : (
            <DetailsForm key={formKey} record={record} definitions={definitions} />
          )}
        </Section>
        <Section id="contact-consent" title="Marketing consent">
          <ConsentList record={record} admin={admin} timezone={timezone} />
        </Section>
        <Section id="contact-timeline" title="Timeline">
          <ContactTimeline contactId={record.id} />
        </Section>
      </div>
    </>
  );
}

function TagsEditor({ record, admin }: { record: ContactRecord; admin: boolean }) {
  const { id: wid } = useCurrentWorkspace();
  const tags = useTags(wid);
  const tag = useTagContact(wid);
  const create = useCreateTag(wid);
  const [name, setName] = useState("");
  const have = new Set(record.tags.map((t) => t.id));
  const available = (tags.data ?? []).filter((t) => !have.has(t.id));

  function change(body: { add?: string[]; remove?: string[] }) {
    tag.mutate({ id: record.id, ...body }, { onError: (error) => toastError(error) });
  }

  function createAndAdd(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    create.mutate(
      { name: name.trim(), color: 0 },
      {
        onSuccess: (made) => {
          setName("");
          change({ add: [made.id] });
        },
        onError: (error) =>
          toastError(error, error instanceof ApiError && error.status === 409 ? "A tag with that name already exists." : undefined),
      },
    );
  }

  return (
    <div className="space-y-3">
      {record.tags.length === 0 ? (
        <p className="text-sm text-fg-secondary">No tags yet.</p>
      ) : (
        <ul aria-label="Tags on this contact" className="flex flex-wrap gap-1.5">
          {record.tags.map((item) => (
            <li key={item.id}>
              <TagChip
                tag={item}
                action={
                  <button
                    type="button"
                    aria-label={`Remove ${item.name}`}
                    className="-mr-1 inline-flex size-5 items-center justify-center rounded-full text-fg-secondary hover:bg-hover hover:text-fg pointer-coarse:size-8"
                    onClick={() => change({ remove: [item.id] })}
                  >
                    <X className="size-3" aria-hidden />
                  </button>
                }
              />
            </li>
          ))}
        </ul>
      )}
      {available.length > 0 ? (
        <Select value="" onValueChange={(value) => change({ add: [value] })}>
          <SelectTrigger aria-label="Add a tag" className="w-full sm:w-56">
            <SelectValue placeholder="Add a tag" />
          </SelectTrigger>
          <SelectContent>
            {available.map((item) => (
              <SelectItem key={item.id} value={item.id}>
                {item.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      ) : null}
      {admin ? (
        <form onSubmit={createAndAdd} className="flex items-center gap-2">
          <Input aria-label="New tag name" placeholder="New tag" maxLength={40} value={name} onChange={(e) => setName(e.target.value)} className="sm:w-56" />
          <Button type="submit" variant="secondary" loading={create.isPending} disabled={!name.trim()}>
            Create and add
          </Button>
        </form>
      ) : null}
    </div>
  );
}

function DetailsForm({ record, definitions }: { record: ContactRecord; definitions: FieldDefinition[] }) {
  const { id: wid } = useCurrentWorkspace();
  const update = useUpdateContact(wid);
  const original = editFrom(record, definitions);
  const [edit, setEdit] = useState<ContactEdit>(original);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const patch = buildPatch(original, edit, definitions);

  function setField(key: string, value: string) {
    setEdit((current) => ({ ...current, fields: { ...current.fields, [key]: value } }));
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!patch) return;
    setErrors({});
    update.mutate(
      { id: record.id, body: patch },
      {
        onSuccess: () => toast.success("Contact saved"),
        onError: (error) => {
          if (error instanceof ApiError && error.errors.length > 0) {
            setErrors(Object.fromEntries(error.errors.map((e) => [e.field, e.message])));
          } else {
            toastError(error);
          }
        },
      },
    );
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-4" aria-label="Contact details">
      <Field invalid={Boolean(errors.email)}>
        <FieldLabel>Email</FieldLabel>
        <Input type="email" maxLength={254} value={edit.email} onChange={(e) => setEdit({ ...edit, email: e.target.value })} />
        {errors.email ? <FieldError>{errors.email}</FieldError> : null}
      </Field>
      <Field invalid={Boolean(errors.phone)}>
        <FieldLabel>Phone</FieldLabel>
        <Input type="tel" maxLength={32} value={edit.phone} onChange={(e) => setEdit({ ...edit, phone: e.target.value })} />
        {errors.phone ? <FieldError>{errors.phone}</FieldError> : null}
      </Field>
      {definitions.map((definition) => (
        <FieldEditor
          key={definition.id}
          definition={definition}
          value={edit.fields[definition.key] ?? ""}
          error={errors[`fields.${definition.key}`]}
          onChange={(value) => setField(definition.key, value)}
        />
      ))}
      <Button type="submit" loading={update.isPending} disabled={!patch}>
        Save changes
      </Button>
    </form>
  );
}

function FieldEditor({
  definition,
  value,
  error,
  onChange,
}: {
  definition: FieldDefinition;
  value: string;
  error?: string;
  onChange: (value: string) => void;
}) {
  return (
    <Field invalid={Boolean(error)}>
      <FieldLabel>{definition.label}</FieldLabel>
      {definition.type === "choice" ? (
        <Select value={value || NONE} onValueChange={(next) => onChange(next === NONE ? "" : next)}>
          <SelectTrigger aria-label={definition.label} className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={NONE}>Not set</SelectItem>
            {definition.options.map((option) => (
              <SelectItem key={option} value={option}>
                {option}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      ) : (
        <Input
          type={definition.type === "date" ? "date" : definition.type === "number" ? "number" : definition.type === "email" ? "email" : definition.type === "phone" ? "tel" : "text"}
          maxLength={500}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
      {error ? <FieldError>{error}</FieldError> : null}
    </Field>
  );
}

function ConsentList({ record, admin, timezone }: { record: ContactRecord; admin: boolean; timezone: string }) {
  const [recording, setRecording] = useState(false);
  return (
    <div className="space-y-3">
      {record.consents.length === 0 ? (
        <p className="text-sm text-fg-secondary">No marketing consent recorded.</p>
      ) : (
        <ul aria-label="Marketing consent" className="space-y-2 text-sm">
          {record.consents.map((consent) => (
            <li key={consent.channel} data-testid="consent-row">
              <p className="font-medium">
                {CHANNEL_LABEL[consent.channel]}: {consent.status === "granted" ? "Agreed" : "Withdrawn"}
              </p>
              <p className="text-xs text-fg-secondary">
                {CONSENT_SOURCE[consent.source]} · {formatDay(consent.occurred_at, timezone)}
                {consent.note ? ` · ${consent.note}` : ""}
              </p>
            </li>
          ))}
        </ul>
      )}
      {admin ? (
        <Button variant="secondary" size="sm" onClick={() => setRecording(true)}>
          Record consent
        </Button>
      ) : null}
      {admin ? <ConsentDialog contactId={record.id} open={recording} onOpenChange={setRecording} /> : null}
    </div>
  );
}

function ConsentDialog({ contactId, open, onOpenChange }: { contactId: string; open: boolean; onOpenChange: (open: boolean) => void }) {
  const { id: wid } = useCurrentWorkspace();
  const record = useRecordConsent(wid);
  const [channel, setChannel] = useState<ConsentChannel>("instagram");
  const [status, setStatus] = useState<"granted" | "revoked">("granted");
  const [note, setNote] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    record.mutate(
      { id: contactId, body: { channel, status, note: note.trim() } },
      {
        onSuccess: () => {
          setNote("");
          onOpenChange(false);
          toast.success("Consent recorded");
        },
        onError: (error) => toastError(error),
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={submit} className="space-y-5">
          <DialogHeader>
            <DialogTitle>Record consent</DialogTitle>
            <DialogDescription>
              Use this when the customer agreed, or withdrew, somewhere else. The note is the proof, so say how it was given.
            </DialogDescription>
          </DialogHeader>
          <Field>
            <FieldLabel>Channel</FieldLabel>
            <Select value={channel} onValueChange={(value) => setChannel(value as ConsentChannel)}>
              <SelectTrigger aria-label="Channel" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(Object.keys(CHANNEL_LABEL) as ConsentChannel[]).map((value) => (
                  <SelectItem key={value} value={value}>
                    {CHANNEL_LABEL[value]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field>
            <FieldLabel>What happened</FieldLabel>
            <Select value={status} onValueChange={(value) => setStatus(value as "granted" | "revoked")}>
              <SelectTrigger aria-label="What happened" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="granted">They agreed</SelectItem>
                <SelectItem value="revoked">They withdrew</SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <Field>
            <FieldLabel>Note</FieldLabel>
            <Textarea required minLength={3} maxLength={300} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Said yes on the shop form" />
          </Field>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={record.isPending} disabled={note.trim().length < 3}>
              Record
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
