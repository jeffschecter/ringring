import logging
import os

import base
import creds_dev
import creds_prod
import index

if os.environ['APPLICATION_ID'].startswith('dev'):
  logging.info("RUNNING IN THE DEV ENVIRONMENT")
  creds = creds_dev
else:
  logging.info("RUNNING IN THE PRODUCTION ENVIRONMENT")
  creds = creds_prod
