# Spend Analyzer




The appliction we developed is called Spend Analyzer and it is a web-based application that helps users to upload their recipts and have a automated track of their expenses with processed reports for managing his spenidings in real time.




The app is built using the **Google Cloud Services**, **Microsoft Azure Form Recognizer**, and **OAuth2** authentication for a personalized and secure user experience.




---




## Features




- Secure login for userd with Google OAuth2.


- Upload receipts to extract and store merchant, transaction, and item details and Total prices which are stored in database


- Personalized **pie charts** for top 5 store-wise purchases.


- Personalized **line charts** for monthly expense trends.


- Secure data storage using Google BigQuery and Google Cloud Storage.


- Clear and Simple User friendly UI


 


---




## Technologies Used




-  **Backend**: Flask (Python)


-  **Frontend**: HTML, CSS, Bootstrap


-  **APIs**:


-  **Google Cloud Services**:


- BigQuery


- Cloud Storage


- OAuth2 Authentication


-  **Microsoft Azure**:


- Form Recognizer API (Azure Document Intelligence)




---




## Prerequisites




### Required Tools


- Python 3.8+


- Flask Framework


- Google Cloud Platform (BigQuery, Storage)


- Microsoft Azure Form Recognizer


- OAuth2 Authentication


- Matplotlib for Data Visualization


- Gunicorn for Deployment


- Git




### Environment Variables


### Required Keys and Configurations


Ensure the following keys and configurations are set in your `.env` file or environment variables:




#### Azure Form Recognizer Credentials:


-  `AZURE_FORM_RECOGNIZER_ENDPOINT` - Your Azure Form Recognizer endpoint.


-  `AZURE_FORM_RECOGNIZER_KEY` - Your Azure Form Recognizer key.




#### Google Cloud Credentials:


-  `GOOGLE_APPLICATION_CREDENTIALS` - Path to your Google credentials JSON file (e.g., `/app/credentials/<Your Google Credentials JSON File>`).


-  `CLIENT_ID` - Your Google OAuth client ID.


-  `CLIENT_SECRET` - Your Google OAuth client secret.


-  `REDIRECT_CALLBACK` - Your deployed app callback URL (e.g., `https://<your-app-url>/callback`).


-  `AUTHORIZATION_BASE_URL` - URL for Google's OAuth authorization (`https://accounts.google.com/o/oauth2/auth`).


-  `TOKEN_URL` - URL for Google's OAuth token exchange (`https://accounts.google.com/o/oauth2/token`).




---




# Setup Guide




1. Clone the Repository




```bash


git clone git@gitlab.com:aashritk/cloud-kondaveeti-aashritk.git


cd cloud-kondaveeti-aashritk


```


 


2. Configure Environment Variables




Create a `.env` file in the project directory with the necessary keys listed above.




Example `.env` file:




```plaintext


AZURE_FORM_RECOGNIZER_ENDPOINT=https://projectoneai.cognitiveservices.azure.com/


AZURE_FORM_RECOGNIZER_KEY=YOUR_AZURE_KEY


GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/cloud-aashritk-credentials.json


CLIENT_ID=YOUR_CLIENT_ID


CLIENT_SECRET=YOUR_CLIENT_SECRET


REDIRECT_CALLBACK=https://spendanalyzer-603254498066.us-central1.run.app/callback


```




3. Install Dependencies




```bash


pip  install  -r  requirements.txt


```




4. Initialize Google Cloud Services




Create a BigQuery Dataset:




```bash


gcloud  bigquery  datasets  create  receipts_dataset  --location=US


```




Create a Storage Bucket:




```bash


gcloud  storage  buckets  create  gs://receipt-uploads-bucket  --location=US


```




5. Run Locally




```bash


python  app.py


```




Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.




# Deployment Instructions




### Step 1: Build Docker Image




```bash


gcloud  builds  submit  --tag  gcr.io/cloud-aashritk/spend-analyzer


```




### Step 2: Deploy to Google Cloud Run




```bash


gcloud  run  deploy  spendanalyzer  \


--image gcr.io/cloud-aashritk/spend-analyzer \


--platform  managed  \


--region us-central1 \


--allow-unauthenticated  \


--set-env-vars AZURE_FORM_RECOGNIZER_ENDPOINT=https://projectoneai.cognitiveservices.azure.com/,AZURE_FORM_RECOGNIZER_KEY=YOUR_AZURE_KEY,GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/cloud-aashritk-credentials.json,CLIENT_ID=YOUR_CLIENT_ID,CLIENT_SECRET=YOUR_CLIENT_SECRET,REDIRECT_CALLBACK=https://spendanalyzer-603254498066.us-central1.run.app/callback


```




### Step 3: Update OAuth Credentials




Set up the Redirect URI in Google Cloud Console under APIs & Services > Credentials:


Add: `https://spendanalyzer-603254498066.us-central1.run.app/callback`




````markdown


## Application Link




[Spend Analyzer Application](https://spendanalyzer-603254498066.us-central1.run.app/)




You can access the Spend Analyzer application using the link above.
