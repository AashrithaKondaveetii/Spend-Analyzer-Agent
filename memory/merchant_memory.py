import logging
from google.cloud import bigquery
from models import FULL_TABLE_ID

class MerchantMemoryService:
    """
    Long-term memory over receipts stored in BigQuery.
    Builds merchant stats: frequency and average spend for a user.
    """

    def __init__(self):
        self.client = bigquery.Client()
        self.logger = logging.getLogger(__name__)

    def get_stats(self, user_email: str, merchant_name: str):
        """
        Returns a dict with merchant stats or None if no history.

        {
          "normalized_name": "starbucks",
          "frequency": 15,
          "avg_spend": 12.34
        }
        """
        query = f"""
            SELECT
                LOWER(`Merchant Name`) AS normalized_name,
                COUNT(*) AS frequency,
                AVG(Total) AS avg_spend
            FROM `{FULL_TABLE_ID}`
            WHERE `User Email` = @user_email
              AND LOWER(`Merchant Name`) = LOWER(@merchant)
              AND Total IS NOT NULL
            GROUP BY normalized_name
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("user_email", "STRING", user_email),
                bigquery.ScalarQueryParameter("merchant", "STRING", merchant_name),
            ]
        )

        self.logger.info("MerchantMemoryService: querying history for %s", merchant_name)
        result = list(self.client.query(query, job_config=job_config))

        if not result:
            return None

        row = result[0]
        return {
            "normalized_name": row.normalized_name,
            "frequency": row.frequency,
            "avg_spend": row.avg_spend,
        }
