#!/usr/bin/env python3

# Copyright (c) Facebook, Inc. and its affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

import json
import re
from datetime import datetime

import requests


def get_ad_archive_id(data):
    """
    Extract ad_archive_id from ad_snapshot_url
    """
    return re.search(r"/\?id=([0-9]+)", data["ad_snapshot_url"]).group(1)


class FbAdsLibraryTraversal:
    default_url_pattern = (
        "https://graph.facebook.com/{}/ads_archive?access_token={}&"
        + "fields={}&search_terms={}&ad_reached_countries={}&search_page_ids={}&"
        + "ad_active_status={}&limit={}"
    )
    default_api_version = "v14.0"

    def __init__(
        self,
        access_token,
        fields,
        search_term,
        country = "TW",
        search_page_ids="",
        ad_active_status="ALL",
        ad_delivery_date_min="2022-01-01",
        ad_delivery_date_max="",
        page_limit=500,
        api_version=None,
        retry_limit=3,
    ):
        self.page_count = 0
        self.access_token = access_token
        self.fields = fields
        self.search_term = search_term
        self.country = country
        self.ad_delivery_date_min = ad_delivery_date_min
        self.ad_delivery_date_max = ad_delivery_date_max
        self.search_page_ids = search_page_ids
        self.ad_active_status = ad_active_status
        self.page_limit = page_limit
        self.retry_limit = retry_limit
        if api_version is None:
            self.api_version = self.default_api_version
        else:
            self.api_version = api_version

    def generate_ad_archives(self):
        next_page_url = self.default_url_pattern.format(
            self.api_version,
            self.access_token,
            self.fields,
            self.search_term,
            self.country,
            self.search_page_ids,
            self.ad_active_status,
            self.page_limit,
        )
        if self.ad_delivery_date_max:
            return self.__class__._get_ad_archives_from_url(
                next_page_url, ad_delivery_date_min=self.ad_delivery_date_min, retry_limit=self.retry_limit,ad_delivery_date_max=self.ad_delivery_date_max
            )
        else:
            return self.__class__._get_ad_archives_from_url(
                next_page_url, ad_delivery_date_min=self.ad_delivery_date_min, retry_limit=self.retry_limit
        )

    @staticmethod
    def _get_ad_archives_from_url(
        next_page_url, ad_delivery_date_min="2022-01-01", retry_limit=3,ad_delivery_date_max=""
    ):
        last_error_url = None
        last_retry_count = 0
        start_time_cutoff_after = datetime.strptime(ad_delivery_date_min, "%Y-%m-%d").timestamp()

        if ad_delivery_date_max:
            start_time_cutoff_before = datetime.strptime(ad_delivery_date_max, "%Y-%m-%d").timestamp()
        else:
            start_time_cutoff_before = ""

        while next_page_url is not None:
            response = requests.get(next_page_url)
            response_data = json.loads(response.text)
            if "error" in response_data:
                if next_page_url == last_error_url:
                    # failed again
                    if last_retry_count >= retry_limit:
                        raise Exception(
                            "Error message: [{}], failed on URL: [{}]".format(
                                json.dumps(response_data["error"]), next_page_url
                            )
                        )
                else:
                    last_error_url = next_page_url
                    last_retry_count = 0
                last_retry_count += 1
                continue
            
            if start_time_cutoff_before:
                filtered = list(
                    filter(
                        lambda ad_archive: ("ad_delivery_start_time" in ad_archive)
                        and (
                            start_time_cutoff_before >=
                            datetime.strptime(
                                ad_archive["ad_delivery_start_time"], "%Y-%m-%d"
                            ).timestamp()
                            >= start_time_cutoff_after
                        ),
                        response_data["data"],
                    )
                )
            else:
                filtered = list(
                    filter(
                        lambda ad_archive: ("ad_delivery_start_time" in ad_archive)
                        and (
                            datetime.strptime(
                                ad_archive["ad_delivery_start_time"], "%Y-%m-%d"
                            ).timestamp()
                            >= start_time_cutoff_after
                        ),
                        response_data["data"],
                    )
                )

            if len(filtered) == 0:
                # if no data after the ad_delivery_date_min, break
                next_page_url = None
                break
            yield filtered

            if "paging" in response_data:
                next_page_url = response_data["paging"]["next"]
            else:
                next_page_url = None

    @classmethod
    def generate_ad_archives_from_url(cls, failure_url, ad_delivery_date_min="2022-01-01"):
        """
        if we failed from error, later we can just continue from the last failure url
        """
        return cls._get_ad_archives_from_url(failure_url, ad_delivery_date_min=ad_delivery_date_min)
