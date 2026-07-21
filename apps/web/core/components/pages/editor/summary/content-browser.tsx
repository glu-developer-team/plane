/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState, useEffect, useCallback, useRef } from "react";
// plane imports
import type { EditorRefApi, IMarking } from "@plane/editor";
import { cn } from "@plane/utils";
// components
import type { THeadingComponentProps } from "./heading-components";
import { OutlineHeading1, OutlineHeading2, OutlineHeading3 } from "./heading-components";

type Props = {
  className?: string;
  emptyState?: React.ReactNode;
  editorRef: EditorRefApi | null;
  setSidePeekVisible?: (sidePeekState: boolean) => void;
  showOutline?: boolean;
};

function getHashSlug(): string | null {
  if (typeof window === "undefined") return null;
  const hash = window.location.hash.replace(/^#/, "").trim();
  return hash || null;
}

function setHashSlug(slug: string) {
  if (typeof window === "undefined") return;
  const nextHash = `#${slug}`;
  if (window.location.hash === nextHash) return;
  window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}${nextHash}`);
}

export function PageContentBrowser(props: Props) {
  const { className, editorRef, emptyState, setSidePeekVisible, showOutline = false } = props;
  // states
  const [headings, setHeadings] = useState<IMarking[]>([]);
  const hasScrolledToInitialHash = useRef(false);

  useEffect(() => {
    const unsubscribe = editorRef?.onHeadingChange(setHeadings);
    // for initial render of this component to get the editor headings
    setHeadings(editorRef?.getHeadings() ?? []);
    return () => {
      unsubscribe?.();
    };
  }, [editorRef]);

  const scrollToSlug = useCallback(
    (slug: string) => {
      if (!editorRef) return false;
      return editorRef.scrollToHeadingBySlug(slug);
    },
    [editorRef]
  );

  useEffect(() => {
    if (!editorRef || headings.length === 0 || hasScrolledToInitialHash.current) return;
    const slug = getHashSlug();
    if (!slug) {
      hasScrolledToInitialHash.current = true;
      return;
    }
    // Wait a frame so the editor layout/scroll container is ready.
    const frame = window.requestAnimationFrame(() => {
      if (scrollToSlug(slug)) hasScrolledToInitialHash.current = true;
    });
    return () => window.cancelAnimationFrame(frame);
  }, [editorRef, headings, scrollToSlug]);

  useEffect(() => {
    const onHashChange = () => {
      const slug = getHashSlug();
      if (slug) scrollToSlug(slug);
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, [scrollToSlug]);

  const handleOnClick = useCallback(
    (event: React.MouseEvent<HTMLAnchorElement>, marking: IMarking) => {
      event.preventDefault();
      setHashSlug(marking.slug);
      editorRef?.scrollSummary(marking);
      setSidePeekVisible?.(false);
    },
    [editorRef, setSidePeekVisible]
  );

  const HeadingComponent: {
    [key: number]: React.FC<THeadingComponentProps>;
  } = {
    1: OutlineHeading1,
    2: OutlineHeading2,
    3: OutlineHeading3,
  };

  if (headings.length === 0) return emptyState ?? null;

  return (
    <div
      className={cn(
        "mt-2 flex h-full flex-col items-start gap-y-1",
        {
          "gap-y-2": showOutline,
        },
        className
      )}
    >
      {headings.map((marking) => {
        const Component = HeadingComponent[marking.level];
        if (!Component) return null;
        if (showOutline === true)
          return (
            <div
              key={`${marking.level}-${marking.sequence}-${marking.slug}`}
              className="h-0.5 flex-shrink-0 self-end rounded-xs bg-layer-3"
              style={{
                width: marking.level === 1 ? "20px" : marking.level === 2 ? "18px" : "14px",
              }}
            />
          );
        return (
          <Component
            key={`${marking.level}-${marking.sequence}-${marking.slug}`}
            marking={marking}
            onClick={(event) => handleOnClick(event, marking)}
          />
        );
      })}
    </div>
  );
}
