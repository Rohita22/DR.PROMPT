# GPT-OSS tokenizer vocabulary

`o200k_base.tiktoken` is OpenAI's official vocabulary used by the `o200k_harmony` encoding for GPT-OSS ordinary text.

- Source: `https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken`
- SHA-256: `446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d`

The vocabulary is stored with the backend so prompt counting requires no runtime network access. Loading verifies the hash before constructing the tokenizer.
