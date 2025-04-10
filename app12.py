from dotenv import load_dotenv
import os
import google.generativeai as genai
import streamlit as st
import pandas as pd
import sqlite3

# ✅ Load environment variables
load_dotenv()

# ✅ Configure Gemini with your API key from environment variables
api_key = os.getenv("Google_API_KEY")
if not api_key:
    st.error("Google API Key not found in environment variables!")
else:
    genai.configure(api_key=api_key)

# ✅ Correct model name (avoid NotFound error)
MODEL_NAME = "models/gemini-2.0-flash-lite"  # Change to "gemini-1.5-pro" if you're using the v1.5 version and have access

prompt = """
You are a SQL expert. Convert the user's natural language request into a valid SQL query.
Assume the database is SQLite and there is a table called 'sales_data' with the following columns:
sale_date, Channel, Product_Name, City, Quantity, Sales.
Only return the SQL query. Do not include explanations or extra text.

Examples:

1. "Show total sales and quantity per city" means:
   SELECT City, SUM(Sales) AS Total_Sales, SUM(Quantity) AS Total_Quantity FROM sales_data GROUP BY City

2. "Which city had the highest sales in 2024" means:
   SELECT City, SUM(Sales) AS Total_Sales FROM sales_data WHERE sale_date BETWEEN '2024-01-01' AND '2024-12-31' GROUP BY City ORDER BY Total_Sales DESC LIMIT 1

3. "Get monthly sales for Product 2 in 2025" means:
   SELECT strftime('%Y-%m', sale_date) AS Month, SUM(Sales) AS Total_Sales FROM sales_data WHERE Product_Name = 'Product 2' AND sale_date BETWEEN '2025-01-01' AND '2025-12-31' GROUP BY Month ORDER BY Month

4. "Show top 3 cities by total quantity sold" means:
   SELECT City, SUM(Quantity) AS Total_Quantity FROM sales_data GROUP BY City ORDER BY Total_Quantity DESC LIMIT 3

5. "List product names with their total sales" means:
   SELECT Product_Name, SUM(Sales) FROM sales_data GROUP BY Product_Name

6. "Find total quantity sold for each channel in the last 6 months" means:
   SELECT Channel, SUM(Quantity) FROM sales_data WHERE sale_date >= date('now', '-6 months') GROUP BY Channel

7. "What is the average sales per transaction for Product 2" means:
   SELECT AVG(Sales) FROM sales_data WHERE Product_Name = 'Product 2'

8. "Rank cities based on total sales" means:
   SELECT City, SUM(Sales) AS Total_Sales, RANK() OVER (ORDER BY SUM(Sales) DESC) AS Rank FROM sales_data GROUP BY City

9. "Get sales in City1 for Channel 1 in October 2024" means:
   SELECT * FROM sales_data WHERE City = 'City1' AND Channel = 'Channel 1' AND sale_date BETWEEN '2024-10-01' AND '2024-10-31'

10. "Compare sales in January and February 2025" means:
    SELECT strftime('%Y-%m', sale_date) AS Month, SUM(Sales) FROM sales_data WHERE sale_date BETWEEN '2025-01-01' AND '2025-02-28' GROUP BY Month

11. "What are the monthly sales across platform1 since Jan 2025?" means:
    SELECT strftime('%Y-%m', sale_date) AS Month, SUM(Sales) AS Total_Sales
    FROM sales_data
    WHERE Channel = 'Channel 1' AND sale_date >= '2025-01-01'
    GROUP BY Month
    ORDER BY Month;

12. "What is the share of units sold across various platforms since Jan 2025?" means:
    SELECT Channel, SUM(Quantity) AS Total_Quantity, (SUM(Quantity) / (SELECT SUM(Quantity) FROM sales_data WHERE sale_date >= '2025-01-01')) * 100 AS Share_Percent
    FROM sales_data
    WHERE sale_date >= '2025-01-01'
    GROUP BY Channel;

13. "Can you tell me the top 5 days with the highest daily units sold?" means:
    SELECT sale_date, SUM(Quantity) AS Total_Quantity
    FROM sales_data
    GROUP BY sale_date
    ORDER BY Total_Quantity DESC
    LIMIT 5;
"""

# ✅ Function to get SQL query from Gemini
def get_gemini_response(question, prompt):
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content([prompt, question])
        # Remove any unwanted formatting or markdown characters from the SQL query
        sql_query = response.text.strip()
        # Clean up the query further if needed
        sql_query = sql_query.replace('```sql', '').replace('```', '').strip()
        return sql_query
    except Exception as e:
        st.error(f"Error generating SQL: {str(e)}")
        return None

# ✅ Function to execute SQL query on SQLite
def read_sqlite_query(sql, db_path):
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        col_names = [description[0] for description in cur.description]
        conn.close()
        return rows, col_names
    except sqlite3.Error as e:
        st.error(f"SQLite Error: {str(e)}")
        return [], []
    except Exception as e:
        st.error(f"General Error: {str(e)}")
        return [], []

# ✅ Function to list all tables in the SQLite database
def list_tables(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cur.fetchall()
        conn.close()
        return tables
    except sqlite3.Error as e:
        st.error(f"SQLite Error while listing tables: {str(e)}")
        return []
    except Exception as e:
        st.error(f"General Error while listing tables: {str(e)}")
        return []

# ✅ Streamlit UI
st.set_page_config(page_title="SQL Assistant")
st.header("🤖 Gemini SQL Query Generator")

# Text input for question
question = st.text_input("🔍 Ask your data question (in plain English):", key="input")

# Button to generate SQL query and run it
submit = st.button("Get SQL & Run")

# SQLite connection path (change to match your SQLite database path)
db_path = "sales_data.db"  # Adjust to your SQLite database file

if submit and question:
    with st.spinner("Generating SQL and fetching data..."):
        sql_query = get_gemini_response(question, prompt)
        
        if sql_query:
            st.subheader("🧠 Generated SQL Query:")
            st.code(sql_query, language="sql")

            # List tables in the SQLite database to check if 'sales_data' exists
            tables = list_tables(db_path)
            
            # Execute SQL query and show results if 'sales_data' exists
            if ('sales_data',) in tables:
                data, columns = read_sqlite_query(sql_query, db_path)

                st.subheader("📊 Query Results:")
                if data:
                    # Check if the number of columns in the data matches the number of columns in the query
                    if len(columns) == len(data[0]):
                        # Convert the data to a format that can be displayed properly
                        df = pd.DataFrame(data, columns=columns)
                        st.dataframe(df)
                    else:
                        st.error("Mismatch between the number of columns in the result and the expected structure.")
                else:
                    st.warning("No data returned.")
            else:
                st.error("Table 'sales_data' does not exist in the database.")
