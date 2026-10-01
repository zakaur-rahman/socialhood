import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Checkbox } from "./checkbox";
import { Field, FieldContent, FieldControl, FieldDescription, FieldError, FieldGroup, FieldLabel } from "./field";
import { Input } from "./input";
import { Label } from "./label";
import { Switch } from "./switch";
import { Textarea } from "./textarea";

const describedBy = (el: HTMLElement) => (el.getAttribute("aria-describedby") ?? "").split(" ").filter(Boolean);

describe("Field", () => {
  it("labels its control through a generated id", () => {
    render(
      <Field>
        <FieldLabel>Workspace name</FieldLabel>
        <Input />
      </Field>,
    );
    const input = screen.getByRole("textbox", { name: "Workspace name" });
    expect(input.id).not.toBe("");
    expect(screen.getByText("Workspace name")).toHaveAttribute("for", input.id);
  });

  it("uses the id it is given, so existing ids (and tests) keep working", () => {
    render(
      <Field id="source-question">
        <FieldLabel>Question</FieldLabel>
        <Input id="source-question" />
      </Field>,
    );
    expect(screen.getByRole("textbox", { name: "Question" })).toHaveAttribute("id", "source-question");
  });

  it("lists the hint and the error in the control's aria-describedby and marks it invalid", () => {
    render(
      <Field>
        <FieldLabel>Web address</FieldLabel>
        <Input />
        <FieldDescription>The main text of the page is read.</FieldDescription>
        <FieldError>Enter a web address that starts with https://</FieldError>
      </Field>,
    );
    const input = screen.getByRole("textbox", { name: "Web address" });
    const hint = screen.getByText("The main text of the page is read.");
    const error = screen.getByRole("alert");
    expect(hint.id).not.toBe("");
    expect(error.id).not.toBe("");
    expect(describedBy(input)).toEqual([hint.id, error.id]);
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription("The main text of the page is read. Enter a web address that starts with https://");
    expect(error).toHaveClass("text-xs", "text-danger-fg");
    expect(hint).toHaveClass("text-xs", "text-fg-secondary");
  });

  it("drops the error from the description and clears aria-invalid once the error is gone", () => {
    const view = (error?: string) => (
      <Field>
        <FieldLabel>Title</FieldLabel>
        <Input />
        <FieldDescription>For example: Shipping policy</FieldDescription>
        <FieldError>{error}</FieldError>
      </Field>
    );
    const { rerender } = render(view("Add a title"));
    const input = screen.getByRole("textbox", { name: "Title" });
    expect(describedBy(input)).toHaveLength(2);
    expect(input).toHaveAttribute("aria-invalid", "true");

    rerender(view(undefined));
    expect(screen.queryByRole("alert")).toBeNull();
    expect(describedBy(input)).toEqual([screen.getByText("For example: Shipping policy").id]);
    expect(input).not.toHaveAttribute("aria-invalid");
  });

  it("keeps the control's own description ids, before the Field's", () => {
    render(
      <>
        <span id="slug-prefix">The address after /w/</span>
        <Field>
          <FieldLabel>URL</FieldLabel>
          <Input aria-describedby="slug-prefix" />
          <FieldDescription>Changing it changes the address of every page.</FieldDescription>
        </Field>
      </>,
    );
    const input = screen.getByRole("textbox", { name: "URL" });
    expect(describedBy(input)).toEqual(["slug-prefix", screen.getByText("Changing it changes the address of every page.").id]);
  });

  it("is invalid when told so, without an error message", () => {
    render(
      <Field invalid>
        <FieldLabel>Name</FieldLabel>
        <Input />
      </Field>,
    );
    expect(screen.getByRole("textbox", { name: "Name" })).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("group")).toHaveAttribute("data-invalid", "true");
  });

  it("shows each validation message once", () => {
    render(
      <Field>
        <FieldLabel>Hashtags</FieldLabel>
        <Input />
        <FieldError errors={[{ message: "Too many hashtags" }, { message: "Too many hashtags" }, undefined, { message: "Remove the spaces" }]} />
      </Field>,
    );
    const items = screen.getAllByRole("listitem");
    expect(items.map((item) => item.textContent)).toEqual(["Too many hashtags", "Remove the spaces"]);
  });

  it("renders no error, and no invalid state, without a message", () => {
    render(
      <Field>
        <FieldLabel>Name</FieldLabel>
        <Input />
        <FieldError errors={[undefined]} />
      </Field>,
    );
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByRole("textbox", { name: "Name" })).not.toHaveAttribute("aria-invalid");
    expect(screen.getByRole("textbox", { name: "Name" })).not.toHaveAttribute("aria-describedby");
  });

  it("wires a textarea, a checkbox and a switch the same way", () => {
    render(
      <FieldGroup>
        <Field>
          <FieldLabel>Answer</FieldLabel>
          <Textarea />
          <FieldError>Add the answer</FieldError>
        </Field>
        <Field orientation="horizontal">
          <Checkbox />
          <FieldLabel>Fetch the page again</FieldLabel>
        </Field>
        <Field orientation="horizontal">
          <FieldContent>
            <FieldLabel>Add a line to automated messages</FieldLabel>
            <FieldDescription>Customers see it at the end.</FieldDescription>
          </FieldContent>
          <Switch />
        </Field>
      </FieldGroup>,
    );
    expect(screen.getByRole("textbox", { name: "Answer" })).toHaveAccessibleDescription("Add the answer");
    expect(screen.getByRole("textbox", { name: "Answer" })).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("checkbox", { name: "Fetch the page again" })).not.toHaveAttribute("aria-invalid");
    expect(screen.getByRole("switch", { name: "Add a line to automated messages" })).toHaveAccessibleDescription("Customers see it at the end.");
  });

  it("toggles a checkbox from its label", async () => {
    render(
      <Field orientation="horizontal">
        <Checkbox />
        <FieldLabel>Fetch the page again</FieldLabel>
      </Field>,
    );
    await userEvent.click(screen.getByText("Fetch the page again"));
    expect(screen.getByRole("checkbox", { name: "Fetch the page again" })).toBeChecked();
  });

  it("wires any other control through FieldControl", () => {
    render(
      <Field>
        <FieldLabel>Timezone</FieldLabel>
        <FieldControl>
          <button type="button" role="combobox" aria-expanded={false} aria-controls="timezones">
            Asia/Kolkata
          </button>
        </FieldControl>
        <FieldDescription>Scheduling uses this timezone.</FieldDescription>
      </Field>,
    );
    const trigger = screen.getByRole("combobox", { name: "Timezone" });
    expect(trigger).toHaveAccessibleDescription("Scheduling uses this timezone.");
  });

  it("leaves a second control with its own id alone", () => {
    render(
      <Field id="amount">
        <FieldLabel>Amount</FieldLabel>
        <Input id="amount" />
        <Input id="unit" aria-label="Unit" />
        <FieldError>Enter a number</FieldError>
      </Field>,
    );
    expect(screen.getByRole("textbox", { name: "Amount" })).toHaveAttribute("aria-invalid", "true");
    const unit = screen.getByRole("textbox", { name: "Unit" });
    expect(unit).toHaveAttribute("id", "unit");
    expect(unit).not.toHaveAttribute("aria-invalid");
    expect(unit).not.toHaveAttribute("aria-describedby");
  });

  it("disables its control and dims its label", () => {
    render(
      <Field disabled>
        <FieldLabel>Workspace name</FieldLabel>
        <Input />
      </Field>,
    );
    expect(screen.getByRole("textbox", { name: "Workspace name" })).toBeDisabled();
    expect(screen.getByRole("group")).toHaveAttribute("data-disabled", "true");
    expect(screen.getByText("Workspace name")).toHaveClass("group-data-[disabled=true]/field:opacity-50");
  });

  it("uses 12 px secondary labels in compact density, the Control role otherwise", () => {
    render(
      <>
        <Field density="compact">
          <FieldLabel>Date</FieldLabel>
          <Input type="date" />
        </Field>
        <Field>
          <FieldLabel>Name</FieldLabel>
          <Input />
        </Field>
      </>,
    );
    expect(screen.getByText("Date")).toHaveClass("text-xs", "text-fg-secondary");
    expect(screen.getByText("Name")).toHaveClass("text-sm", "font-medium");
    expect(screen.getByText("Name")).not.toHaveClass("text-xs");
  });

  it("stacks label, control and messages 6 px apart, and fields 16 px apart in a FieldGroup", () => {
    render(
      <FieldGroup data-testid="group">
        <Field>
          <FieldLabel>Name</FieldLabel>
          <Input />
        </Field>
      </FieldGroup>,
    );
    expect(screen.getByTestId("group")).toHaveClass("flex-col", "gap-4");
    expect(screen.getByRole("group")).toHaveClass("flex-col", "gap-1.5");
  });
});

describe("Label", () => {
  it("has normal leading, so a wrapped label doesn't clip", () => {
    render(<Label htmlFor="x">A label long enough to wrap onto a second line on a phone</Label>);
    const label = screen.getByText(/A label long enough/);
    expect(label).toHaveClass("text-sm", "font-medium");
    expect(label.className).not.toMatch(/\bleading-none\b/);
  });
});
