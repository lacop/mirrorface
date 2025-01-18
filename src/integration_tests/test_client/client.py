# TODO: Behavior from cmdline / env vars. Should be a generic test base.

from transformers import AutoModel

model = AutoModel.from_pretrained("prajjwal1/bert-tiny")

print("MIRRORFACE-TEST-CLIENT:PASS")
