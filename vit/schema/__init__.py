"""Schema version tracking + migration registry.

Every vit project has a schema_version in .vit/config.json. When vit is
upgraded and the shape of the JSON domain files or config changes in a
breaking way, we bump CURRENT_SCHEMA_VERSION and add a migration that
transforms old data into the new shape.

Migrations run lazily when a project is loaded — not on import — so old
repos stay on disk unchanged until they're actually opened by a newer
vit. That lets two people on different vit versions coexist temporarily
without one corrupting the other's working copy.
"""

from __future__ import annotations

CURRENT_SCHEMA_VERSION = 1
"""Bumped on breaking changes to the on-disk JSON shape.

Change log:
  1 — initial schema: cuts/color/audio/effects/markers/metadata/manifest
      with .vit/config.json containing schema_version + vit_version + nle.
"""
