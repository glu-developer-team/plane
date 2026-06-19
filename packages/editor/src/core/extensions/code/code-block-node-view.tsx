/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { NodeViewProps } from "@tiptap/react";
import { NodeViewContent, NodeViewWrapper } from "@tiptap/react";
import { CheckIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { ChevronDownIcon, ChevronUpIcon, CopyIcon } from "@plane/propel/icons";
import { Tooltip } from "@plane/propel/tooltip";
import { cn } from "@plane/utils";
import { MermaidDiagram } from "@/components/mermaid/mermaid-diagram";
import { normalizeMermaidSource } from "./utils/normalize-mermaid-source";
import type { TCodeBlockAttributes } from "./types";
import { ECodeBlockAttributeNames } from "./types";

export function CodeBlockComponent(props: NodeViewProps) {
  const { node, editor } = props;
  const [copied, setCopied] = useState(false);
  const attrs = node.attrs as TCodeBlockAttributes;
  const language = attrs[ECodeBlockAttributeNames.LANGUAGE];
  const isMermaid = language === "mermaid";
  const isEditable = editor.isEditable;
  const rawSource = node.textContent;
  const source = isMermaid ? normalizeMermaidSource(rawSource) : rawSource;
  const hasSource = Boolean(source.trim());
  const [isSourceExpanded, setIsSourceExpanded] = useState(!hasSource);
  const hadSourceRef = useRef(hasSource);

  useEffect(() => {
    if (!hadSourceRef.current && hasSource) {
      setIsSourceExpanded(false);
    }

    if (!hasSource) {
      setIsSourceExpanded(true);
    }

    hadSourceRef.current = hasSource;
  }, [hasSource]);

  const expandSource = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsSourceExpanded(true);
    window.setTimeout(() => {
      editor.chain().focus().run();
    }, 0);
  };

  const collapseSource = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsSourceExpanded(false);
  };

  const copyToClipboard = async (e: React.MouseEvent<HTMLButtonElement, MouseEvent>) => {
    try {
      await navigator.clipboard.writeText(node.textContent);
      setCopied(true);
      setTimeout(() => setCopied(false), 1000);
    } catch {
      setCopied(false);
    }
    e.preventDefault();
    e.stopPropagation();
  };

  if (isMermaid) {
    if (!isEditable) {
      return (
        <NodeViewWrapper
          key={attrs[ECodeBlockAttributeNames.ID]}
          className="code-block mermaid-block group/code relative"
        >
          <Tooltip tooltipContent="Copy diagram source">
            <button
              type="button"
              className={cn(
                "group/button absolute top-2 right-2 z-10 hidden size-8 items-center justify-center rounded-md border border-subtle bg-layer-1 backdrop-blur-sm transition duration-150 ease-in-out group-hover/code:flex",
                {
                  "bg-success-subtle hover:bg-success-subtle-1 active:bg-success-subtle-1": copied,
                }
              )}
              onClick={(e) => void copyToClipboard(e)}
            >
              {copied ? (
                <CheckIcon className="h-3 w-3 text-success-primary" strokeWidth={3} />
              ) : (
                <CopyIcon className="h-3 w-3 text-tertiary group-hover/button:text-primary" />
              )}
            </button>
          </Tooltip>

          <MermaidDiagram source={source} />
          <NodeViewContent as="code" className="hidden" />
        </NodeViewWrapper>
      );
    }

    return (
      <NodeViewWrapper
        key={attrs[ECodeBlockAttributeNames.ID]}
        className="code-block mermaid-block group/code relative"
      >
        <Tooltip tooltipContent="Copy diagram source">
          <button
            type="button"
            className={cn(
              "group/button absolute top-2 right-2 z-10 hidden size-8 items-center justify-center rounded-md border border-subtle bg-layer-1 backdrop-blur-sm transition duration-150 ease-in-out group-hover/code:flex",
              {
                "bg-success-subtle hover:bg-success-subtle-1 active:bg-success-subtle-1": copied,
              }
            )}
            onClick={(e) => void copyToClipboard(e)}
          >
            {copied ? (
              <CheckIcon className="h-3 w-3 text-success-primary" strokeWidth={3} />
            ) : (
              <CopyIcon className="h-3 w-3 text-tertiary group-hover/button:text-primary" />
            )}
          </button>
        </Tooltip>

        {hasSource && <MermaidDiagram source={source} />}

        {hasSource && (
          <div className="mt-2 flex items-center">
            <button
              type="button"
              contentEditable={false}
              className="text-xs inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-tertiary transition duration-150 ease-in-out hover:bg-layer-2 hover:text-primary"
              onClick={isSourceExpanded ? collapseSource : expandSource}
              aria-expanded={isSourceExpanded}
            >
              {isSourceExpanded ? (
                <>
                  <ChevronUpIcon className="size-3.5" />
                  Hide source
                </>
              ) : (
                <>
                  <ChevronDownIcon className="size-3.5" />
                  Show source
                </>
              )}
            </button>
          </div>
        )}

        <pre
          className={cn("rounded-lg bg-layer-3 p-4 text-primary", {
            "mt-2": !hasSource || isSourceExpanded,
            hidden: hasSource && !isSourceExpanded,
          })}
        >
          <NodeViewContent as="code" className="whitespace-pre-wrap" />
        </pre>
      </NodeViewWrapper>
    );
  }

  return (
    <NodeViewWrapper key={attrs[ECodeBlockAttributeNames.ID]} className="code-block group/code relative">
      <Tooltip tooltipContent="Copy code">
        <button
          type="button"
          className={cn(
            "group/button absolute top-2 right-2 z-10 hidden size-8 items-center justify-center rounded-md border border-subtle bg-layer-1 backdrop-blur-sm transition duration-150 ease-in-out group-hover/code:flex",
            {
              "bg-success-subtle hover:bg-success-subtle-1 active:bg-success-subtle-1": copied,
            }
          )}
          onClick={(e) => void copyToClipboard(e)}
        >
          {copied ? (
            <CheckIcon className="h-3 w-3 text-success-primary" strokeWidth={3} />
          ) : (
            <CopyIcon className="h-3 w-3 text-tertiary group-hover/button:text-primary" />
          )}
        </button>
      </Tooltip>

      <pre className="my-2 rounded-lg bg-layer-3 p-4 text-primary">
        <NodeViewContent as="code" className="whitespace-pre-wrap" />
      </pre>
    </NodeViewWrapper>
  );
}
