#!/usr/bin/python

import os
import pip
import shutil
import sys


def main():
  basedir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
  lib_dir = os.path.join(basedir, "lib/")
  pip.main(["install", "--upgrade", "-t", lib_dir, basedir])
  print "Installed {} to {}".format(basedir, lib_dir)


if __name__ == "__main__":
  main()