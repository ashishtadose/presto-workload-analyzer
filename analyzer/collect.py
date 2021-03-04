#!/usr/bin/env python3

# Copyright (c) 2019-2021 Varada, Inc.
# This file is part of Presto Workload Analyzer.
#
# Presto Workload Analyzer is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Presto Workload Analyzer is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Presto Workload Analyzer.  If not, see <https://www.gnu.org/licenses/>.

import argparse
import gzip
import pathlib
import sys
import time
import logbook
import requests
from requests.auth import HTTPBasicAuth

logbook.StreamHandler(sys.stderr).push_application()
log = logbook.Logger("collect")


def get(url, username, password):
    # User header is required by latest Presto versions.
    req_headers = headers={
        "X-Presto-User": "analyzer",
        "X-Trino-User": "analyzer",
    }

    if all([username, password]):
        response = requests.get(url, req_headers, auth=HTTPBasicAuth(
            username,
            password))
    else:
        response = requests.get(url, req_headers)

    if not response.ok:
        log.warn("HTTP {} {} for url: {}", response.status_code, response.reason, url)
        return None
    else:
        return response


def main():
    p = argparse.ArgumentParser()
    p.add_argument("-c", "--coordinator", default="http://localhost:8080")
    p.add_argument("-e", "--query-endpoint", default="/v1/query")
    p.add_argument("-u", "--username")
    p.add_argument("-p", "--password")
    p.add_argument("-o", "--output-dir", default="JSONs", type=pathlib.Path)
    p.add_argument("-d", "--delay", default=0.1, type=float)
    p.add_argument("--loop", default=False, action="store_true")
    p.add_argument("--loop-delay", type=float, default=1.0)
    args = p.parse_args()

    endpoint = "{}{}".format(args.coordinator, args.query_endpoint)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    done_state = {"FINISHED", "FAILED"}
    while True:
        # Download last queries' IDs:
        response = get(endpoint, args.username, args.password)
        if not response:
            return
        ids = [q["queryId"] for q in response.json() if q["state"] in done_state]
        log.debug("Found {} queries", len(ids))

        # Download new queries only:
        for query_id in sorted(ids):
            output_file = args.output_dir / (query_id + ".json.gz")  # to save storage
            if output_file.exists():  # don't download already downloaded JSONs
                continue

            url = "{}/{}?pretty".format(endpoint, query_id)  # human-readable JSON
            time.sleep(args.delay)  # for rate-limiting
            log.info("Downloading {} -> {}", url, output_file)
            try:
                response = get(endpoint, args.username, args.password)
                if not response:
                    continue
            except Exception:
                log.exception("Failed to download {}", query_id)
                continue

            with gzip.open(output_file.open("wb"), "wb") as f:
                f.write(response.content)

        if args.loop:
            time.sleep(args.loop_delay)
        else:
            break


if __name__ == "__main__":
    main()
