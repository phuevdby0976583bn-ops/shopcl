"""
Patch for Starlette / FastAPI multipart and form parsing limits.
By default, recent versions of Starlette enforce a strict 1024KB (1MB) limit on form fields:
"Part exceeded maximum size of 1024KB."

This module raises the limits globally to 500MB, 200,000 fields, and 50,000 files,
allowing bulk upload of 100,000+ accounts/lines without hitting HTTP 400.
"""

import logging
import starlette.formparsers as fp
import starlette.requests as req

logger = logging.getLogger(__name__)

MAX_PART_SIZE = 500 * 1024 * 1024  # 500 MB
MAX_FIELDS = 200000
MAX_FILES = 50000
SPOOL_MAX_SIZE = 500 * 1024 * 1024  # 500 MB

# 1. Update class attributes on MultiPartParser
try:
    fp.MultiPartParser.max_part_size = MAX_PART_SIZE
    fp.MultiPartParser.spool_max_size = SPOOL_MAX_SIZE
    fp.MultiPartParser.max_files = MAX_FILES
    fp.MultiPartParser.max_fields = MAX_FIELDS
except Exception as e:
    logger.debug(f"Failed to set MultiPartParser attributes: {e}")

# 2. Update __kwdefaults__ on MultiPartParser and FormParser
if hasattr(fp.MultiPartParser.__init__, "__kwdefaults__") and fp.MultiPartParser.__init__.__kwdefaults__:
    fp.MultiPartParser.__init__.__kwdefaults__["max_part_size"] = MAX_PART_SIZE
    fp.MultiPartParser.__init__.__kwdefaults__["max_fields"] = MAX_FIELDS
    fp.MultiPartParser.__init__.__kwdefaults__["max_files"] = MAX_FILES

if hasattr(fp.FormParser.__init__, "__kwdefaults__") and fp.FormParser.__init__.__kwdefaults__:
    fp.FormParser.__init__.__kwdefaults__["max_part_size"] = MAX_PART_SIZE
    fp.FormParser.__init__.__kwdefaults__["max_fields"] = MAX_FIELDS

# 3. Update __kwdefaults__ on Request.form and Request._get_form
if hasattr(req.Request.form, "__kwdefaults__") and req.Request.form.__kwdefaults__:
    req.Request.form.__kwdefaults__["max_part_size"] = MAX_PART_SIZE
    req.Request.form.__kwdefaults__["max_fields"] = MAX_FIELDS
    req.Request.form.__kwdefaults__["max_files"] = MAX_FILES

if hasattr(req.Request._get_form, "__kwdefaults__") and req.Request._get_form.__kwdefaults__:
    req.Request._get_form.__kwdefaults__["max_part_size"] = MAX_PART_SIZE
    req.Request._get_form.__kwdefaults__["max_fields"] = MAX_FIELDS
    req.Request._get_form.__kwdefaults__["max_files"] = MAX_FILES

# 4. Wrap MultiPartParser.__init__ to ensure any direct instantiation respects MAX_PART_SIZE
_orig_multipart_init = fp.MultiPartParser.__init__

def _patched_multipart_init(
    self,
    headers,
    stream,
    *,
    max_files=MAX_FILES,
    max_fields=MAX_FIELDS,
    max_part_size=MAX_PART_SIZE,
):
    if max_part_size is not None and max_part_size < MAX_PART_SIZE:
        max_part_size = MAX_PART_SIZE
    if max_fields is not None and max_fields < MAX_FIELDS:
        max_fields = MAX_FIELDS
    if max_files is not None and max_files < MAX_FILES:
        max_files = MAX_FILES
    return _orig_multipart_init(
        self,
        headers,
        stream,
        max_files=max_files,
        max_fields=max_fields,
        max_part_size=max_part_size,
    )

fp.MultiPartParser.__init__ = _patched_multipart_init

# 5. Wrap FormParser.__init__
_orig_formparser_init = fp.FormParser.__init__

def _patched_formparser_init(
    self,
    headers,
    stream,
    *,
    max_fields=MAX_FIELDS,
    max_part_size=MAX_PART_SIZE,
):
    if max_part_size is not None and max_part_size < MAX_PART_SIZE:
        max_part_size = MAX_PART_SIZE
    if max_fields is not None and max_fields < MAX_FIELDS:
        max_fields = MAX_FIELDS
    return _orig_formparser_init(
        self,
        headers,
        stream,
        max_fields=max_fields,
        max_part_size=max_part_size,
    )

fp.FormParser.__init__ = _patched_formparser_init

# 6. Wrap Request._get_form to ensure any call to request.form() receives MAX_PART_SIZE
_orig_get_form = req.Request._get_form

async def _patched_get_form(
    self,
    *,
    max_files: int | float = MAX_FILES,
    max_fields: int | float = MAX_FIELDS,
    max_part_size: int = MAX_PART_SIZE,
):
    if max_part_size is not None and max_part_size < MAX_PART_SIZE:
        max_part_size = MAX_PART_SIZE
    if max_fields is not None and max_fields < MAX_FIELDS:
        max_fields = MAX_FIELDS
    if max_files is not None and max_files < MAX_FILES:
        max_files = MAX_FILES
    return await _orig_get_form(
        self,
        max_files=max_files,
        max_fields=max_fields,
        max_part_size=max_part_size,
    )

req.Request._get_form = _patched_get_form

logger.info(f"Multipart limit successfully patched to {int(MAX_PART_SIZE / (1024 * 1024))}MB")
