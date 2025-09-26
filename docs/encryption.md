# Data encryption in pyFADE

## Dataset encryption via SQLCipher

pyFADE supports encrypting datasets using SQLCipher, which is an extension to SQLite that provides transparent 256-bit AES encryption of database files. This ensures that all data stored in the dataset is encrypted at rest, protecting sensitive information from unauthorized access.

To use SQLCipher encryption in pyFADE, the following steps are necessary:
- The `sqlcipher3` Python package must be installed. On Windows, it requires compiling it from source, which can be complex. Precompiled binaries are available for some platforms.
- When creating or opening a dataset, a password must be provided. This password is used to derive the encryption key.
- Non-encrypted datasets can be encrypted at any moment via **File → Encrypt and Save As…**, which writes a SQLCipher copy without modifying the original file.
- Encrypted datasets expose **File → Change Password…** to rotate credentials in place and **File → Save Unencrypted Copy As…** to create a plain SQLite export.
- After any encryption state change the workspace prompts you to reopen the dataset so cached state and active widgets refresh cleanly.

## Exported datasets encryption

When exporting datasets, pyFADE can create encrypted ZIP archives. This provides an additional layer of security when sharing or backing up datasets.
Encryption may be enabled in the export template settings, so it is applied automatically during export every time.
Export archive encryption uses standard ZIP encryption with a password, password may be stored in the export template or asked from the user at export time. If Dataset encryption is enabled, it means stored password is encrypted too, so it is not accessible without the dataset password.

