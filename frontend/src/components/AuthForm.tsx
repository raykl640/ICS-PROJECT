import type { FormEvent, ReactNode } from "react";
import { PageTitle } from "../app/PageTitle";
import { Notice } from "../design/components/Display";

interface AuthFormProps {
  title: string;
  intro?: ReactNode;
  error: string | null;
  onSubmit: () => void;
  children: ReactNode;
  footer?: ReactNode;
}

/** Card layout shared by sign-in, sign-up, recovery and unlock: title, intro, error notice, fields, links. */
export function AuthForm({ title, intro, error, onSubmit, children, footer }: AuthFormProps) {
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit();
  };
  return (
    <div className="mx-auto flex w-full max-w-md flex-col gap-4 rounded-lg border border-line-subtle bg-raised shadow-raised p-6 sm:p-8">
      <PageTitle>{title}</PageTitle>
      {intro && <div className="text-ink-muted">{intro}</div>}
      {error && (
        <div role="alert">
          <Notice tone="danger">{error}</Notice>
        </div>
      )}
      <form noValidate onSubmit={submit} className="flex flex-col gap-4">
        {children}
      </form>
      {footer && <div className="flex flex-col gap-2 border-t border-line-subtle pt-4">{footer}</div>}
    </div>
  );
}
