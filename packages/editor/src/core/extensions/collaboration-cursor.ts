/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { HocuspocusProvider } from "@hocuspocus/provider";
import { Extension } from "@tiptap/core";
import { yCursorPlugin } from "y-prosemirror";
// types
import type { TUserDetails } from "@/types";

type TArgs = {
  provider: HocuspocusProvider;
  user: TUserDetails;
};

export const CollaborationCursorExtension = ({ provider, user }: TArgs) =>
  Extension.create({
    name: "collaborationCursor",

    onCreate() {
      provider.awareness?.setLocalStateField("user", user);
    },

    addProseMirrorPlugins() {
      const awareness = provider.awareness;
      if (!awareness) return [];
      return [
        yCursorPlugin(awareness, {
          cursorBuilder: (remoteUser: TUserDetails) => {
            const cursor = document.createElement("span");
            cursor.className = "collaboration-cursor__caret";
            cursor.style.setProperty("--collaboration-user-color", remoteUser.color);

            const label = document.createElement("span");
            label.className = "collaboration-cursor__label";
            label.textContent = remoteUser.name || "Anonymous";
            cursor.appendChild(label);
            return cursor;
          },
          selectionBuilder: (remoteUser: TUserDetails) => ({
            class: "collaboration-cursor__selection",
            style: `--collaboration-user-color: ${remoteUser.color}`,
          }),
        }),
      ];
    },
  });
