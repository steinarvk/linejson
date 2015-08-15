Command-line utility to work with files that contain JSON records on each line.

Commands
--------

*grep*:
Filter by a (regex) pattern on a particular key.

*extract*:
(non-JSON output)
Pull one or more keys out of the JSON records.

*uniq*:
(non-JSON output)
Find all the unique values corresponding to a particular key, and optionally
their counts. Note that all the distinct values will need to be kept in
memory.

*replace*:
Perform a regex substitution on a particular key, with the output saved to
that same key or a different one.

*compare*:
Filter by a value comparison (e.g. numeric) between a value from the JSON and
a constant Python value, or between two values from the JSON.

Notes
-----
This is intended for quick-and-dirty record processing. JSON is nice and
readable, but due to all the parsing and formatting going on, pipelines built
with this tool are horrendously inefficient.

Usage example
-------------

```
$ cat | \
  python -mlinejson compare species eq cat -s | \
  python -mlinejson grep -v breed "N.*" | \
  python -mlinejson extract name breed --require
{"species": "cat", "name": "Crookshanks", "breed": "Himalayan Persian"}
{"species": "dog", "name": "Hachiko", "breed": "Akita"}
{"species": "cat", "name": "Pangur Ban"}
{"species": "cat", "name": "Tama", "breed": "Calico"}
{"species": "dog", "name": "Hachiko", "breed": "Akita"}
{"species": "cat", "name": "Larissa", "breed": "Norwegian forest cat"}
{"species": "cat", "name": "Tom", "breed": "Domestic short-haired cat"}
^D
Crookshanks "Himalayan Persian"
Tama Calico
Tom "Domestic short-haired cat"
```
