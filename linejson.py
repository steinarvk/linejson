#!/usr/bin/env python

"""Command-line tool for processing files with a JSON record on every line."""

__author__ = "Steinar V. Kaldager"
__version__ = "0.0.1"

import json
import sys
import ast
import collections
import argparse
import re
import operator
import csv
import contextlib
import codecs
import logging

def on_lines_in(filename, callback):
  if filename and not filename == "-":
    with codecs.open(filename, "r", encoding="utf-8") as f:
      for line in f:
        callback(line)
  else:
    for line in codecs.getreader("utf-8")(sys.stdin):
      callback(line)

class JsonFilter(object):
  def __init__(self, args, out):
    self.out = codecs.getwriter("utf-8")(sys.stdout)

  def write(self, data):
    print >>self.out, json.dumps(data)

class PassthroughFilter(JsonFilter):
  def __init__(self, args, out):
    JsonFilter.__init__(self, args, out)

  def __call__(self, data):
    if self.accept(data):
      self.write(data)

class Grepper(PassthroughFilter):
  def __init__(self, args, out):
    PassthroughFilter.__init__(self, args, out)
    if args.literal:
      self.check_match = lambda s: s == args.pattern
    else:
      self.check_match = re.compile(args.pattern).match
    self.key = args.key

  def accept(self, data):
    match = self.check_match(data.get(self.key, ""))
    return bool(match) ^ bool(args.invert)

class Comparator(PassthroughFilter):
  Operators = {
    "gt": operator.gt,
    "ge": operator.ge,
    "lt": operator.lt,
    "le": operator.le,
    "eq": operator.eq,
    "ne": operator.ne,
  }

  def __init__(self, args, out):
    PassthroughFilter.__init__(self, args, out)
    self.key = args.key
    self.op = Comparator.Operators[args.operator]
    if args.string:
      self.get_value = lambda _: args.value
    else:
      try:
        value = ast.literal_eval(args.value)
        self.get_value = lambda _: value
      except ValueError:
        self.key2 = args.value
        self.get_value = operator.itemgetter(self.key2)

  def accept(self, data):
    v1 = data.get(self.key)
    if v1 is None:
      return False
    v2 = self.get_value(data)
    return self.op(v1, v2)

class Replacer(JsonFilter):
  def __init__(self, args, out):
    JsonFilter.__init__(self, args, out)
    self.key = args.key
    self.output_key = args.output or self.key
    self.regex = re.compile(args.pattern)
    self.repl = args.replacement

  def __call__(self, data):
    val = self.regex.sub(self.repl, data.get(self.key, ""))
    data[self.output_key] = val
    self.write(data)

class Extractor(object):
  def __init__(self, args, out):
    self.keys = args.key
    self.required = args.require
    if len(self.keys) == 1:
      self.out = codecs.getwriter("utf-8")(sys.stdout)
    else:
      self.out = csv.writer(out, delimiter="," if args.csv else " ")

  def write(self, row):
    if len(row) == 1:
      print >>self.out, row[0].encode("utf-8")
    else:
      self.out.writerow(row)

  def __call__(self, data):
    if not self.required or all(k in data for k in self.keys):
      self.write([data.get(key, "").encode("utf-8") for key in self.keys])

class Uniq(object):
  def __init__(self, args, out):
    self.key = args.key
    self.counts = args.count
    self.out = codecs.getwriter("utf-8")(sys.stdout)
    self.seen = collections.Counter()

  def __call__(self, data):
    self.seen[data.get(self.key)] += 1

  def finish(self):
    if self.counts:
      items = self.seen.items()
      items.sort(key=operator.itemgetter(1))
      for key, value in items:
        print >>self.out, key, value
    else:
      keys = sorted(self.seen.keys())
      for key in keys:
        print >>self.out, key

def main(args, out):
  cmd = args.command(args, out)
  def process_line(line):
    cmd(json.loads(line))
  on_lines_in(args.filename, process_line)
  try:
    finish = cmd.finish
  except AttributeError:
    pass
  else:
    finish()

def make_grep_parser(subparsers):
  parser = subparsers.add_parser("grep",
    help="filter by a regex on a particular key")
  parser.set_defaults(command=Grepper)
  parser.add_argument("key", metavar="KEY",
    help="key to match against")
  parser.add_argument("pattern", metavar="PATTERN",
    help="pattern to filter by")
  parser.add_argument("--literal", action="store_true",
    help="literal match (no regex)")
  parser.add_argument("--invert", "-v", action="store_true",
    help="whether to invert matching")
  return parser

def make_compare_parser(subparsers):
  parser = subparsers.add_parser("compare",
    help="filter by value comparison")
  parser.set_defaults(command=Comparator)
  parser.add_argument("key", metavar="KEY",
    help="key to filter by")
  parser.add_argument("operator", metavar="OP",
    choices=Comparator.Operators.keys(),
    help="operator with which to compare")
  parser.add_argument("value", metavar="VALUE",
    help="value or key to filter by")
  parser.add_argument("--string", "-s", action="store_true",
    help="force value to be interpreted as string")

def make_replace_parser(subparsers):
  parser = subparsers.add_parser("replace",
    help="replace by a regex in a particular key")
  parser.set_defaults(command=Replacer)
  parser.add_argument("key", metavar="KEY",
    help="key to match against")
  parser.add_argument("pattern", metavar="PATTERN",
    help="regex pattern to filter by")
  parser.add_argument("replacement", metavar="REPL",
    help="substitution expression (backreferences: \\1 ..)")
  parser.add_argument("--output",
    help="output key (default: same as input key)")
  return parser

def make_extract_parser(subparsers):
  parser = subparsers.add_parser("extract",
    help="extract a key or a set of keys from the JSON")
  parser.set_defaults(command=Extractor)
  parser.add_argument("key", metavar="KEY", nargs="+",
    help="key(s) to extract")
  parser.add_argument("--require", action="store_true",
    help="require all keys to be present")
  parser.add_argument("--csv", action="store_true",
    help="use CSV format for output (instead of separating with spaces)")
  return parser

def make_uniq_parser(subparsers):
  parser = subparsers.add_parser("uniq",
    help="find (and optionally count) the range of values of a particular key")
  parser.set_defaults(command=Uniq)
  parser.add_argument("key", metavar="KEY",
    help="key to extract")
  parser.add_argument("--count", "-c", action="store_true",
    help="count occurrences and sort by frequency")
  return parser

def make_parser():
  parser = argparse.ArgumentParser("linejson")
  subparsers = parser.add_subparsers()
  parser.add_argument("--filename", metavar="FILE",
    help="input filename (if none, reads from stdin)")
  make_grep_parser(subparsers)
  make_extract_parser(subparsers)
  make_uniq_parser(subparsers)
  make_replace_parser(subparsers)
  make_compare_parser(subparsers)
  return parser

if __name__ == '__main__':
  args = make_parser().parse_args()
  main(args, sys.stdout)
