# Install necessary libraries
# !pip install pymongo flask sentence-transformers pandas fuzzywuzzy[speedup] rapidfuzz

from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
from sentence_transformers import SentenceTransformer, util
from fuzzywuzzy import fuzz  # For fuzzy matching
import pandas as pd
import re
import mysql.connector
import pandas as pd
import ast
import cohere
from flask_session import Session
from flask import Flask, render_template, request, session, redirect, url_for

app = Flask(__name__)

# MongoDB Cluster Connections
client1 = MongoClient(
    "mongodb+srv://shubham21099:OoaZmPV3SHKCTFF8@rpms-1.upidh.mongodb.net/?retryWrites=true&w=majority&appName=RPMS-1")
client2 = MongoClient(
    "mongodb+srv://parveen21079:IqOtVWtlL07iko7b@rpms-3.sfebr.mongodb.net/?retryWrites=true&w=majority&appName=RPMS-3")
db1 = client1['RPMS-1']
db2 = client2['RPMS-3']

# Central Schema (Predefined)
central_schema = {
    'title': 'string',
    'authors': 'string',
    'affiliation': 'string',
    'abstract': 'string',
    'date': 'date',
    'published_date': 'date',
    'doi': 'string',
    'publisher_organization': 'string',
    'url': 'string',
    'issn': 'string',
    'license': 'string',
    'ref_count': 'int',
    'subject': 'string',
    'type': 'string',
    'volume': 'string',
    'issue': 'string',
    'created_date': 'date',
    'keywords': 'string',
}

# Initialize Sentence Transformer
model = SentenceTransformer('all-MiniLM-L6-v2')

# Function to extract schema dynamically from MongoDB collection


def extract_schema(collection):
    sample_document = collection.find_one()
    if not sample_document:
        return {}
    # Infers data types based on a sample document
    schema = {field: type(value).__name__ for field,
              value in sample_document.items()}
    return schema


# Retrieve schemas dynamically from MongoDB collections
schemas = {
    'schema1': extract_schema(db1['IEEE']),
    'schema2': extract_schema(db2['ResearchGate'])
}

# Helper function for computing schema similarity using sentence embeddings


def compute_similarity(schema_a, schema_b):
    embeddings_a = model.encode([str(col) for col in schema_a])
    embeddings_b = model.encode([str(col) for col in schema_b])
    cosine_sim = util.cos_sim(embeddings_a, embeddings_b).cpu().numpy()
    return pd.DataFrame(cosine_sim, index=schema_a, columns=schema_b)

# Get best matches for schema mappings


def get_best_matches(similarity_df):
    matches = {}
    for col_a in similarity_df.index:
        best_match = similarity_df.loc[col_a].idxmax()
        matches[col_a] = best_match
    return matches


# Generate schema mappings dynamically
mappings = {}
# for schema_name, schema in schemas.items():
#     similarity_df = compute_similarity(
#         list(central_schema.keys()), list(schema.keys()))
#     mappings[schema_name] = get_best_matches(similarity_df)

# Add MySQL Connection
mysql_config = {
    'user': 'root',       # Replace with your MySQL username
    'password': 'IIA',   # Replace with your MySQL password
    # Replace with your MySQL host (e.g., public IP or domain name)
    'host': '34.44.14.55',
    'database': 'research_papers'    # Replace with your MySQL database name
}
mysql_conn = mysql.connector.connect(**mysql_config)
mysql_cursor = mysql_conn.cursor(dictionary=True)

# Function to extract schema dynamically from MySQL


def extract_mysql_schema(cursor, table_name):
    cursor.execute(f"DESCRIBE {table_name}")
    schema = {row['Field']: row['Type'] for row in cursor.fetchall()}
    return schema


# Retrieve MySQL schema dynamically
mysql_table_name = 'CVPR_temp'  # Replace with your MySQL table name


# schemas['schema3'] = extract_mysql_schema(mysql_cursor, mysql_table_name)

# # Generate schema mappings for MySQL
# similarity_df_mysql = compute_similarity(
#     list(central_schema.keys()), list(schemas['schema3'].keys()))
# mappings['schema3'] = get_best_matches(similarity_df_mysql)

# Parse comma-separated values


def parse_comma_separated_values(value):
    return [item.strip() for item in value.split(',')]

# Build MongoDB query with regex and fuzzy matching


# def build_query(query_params, mapping, fuzzy=False):
#     query = {}
#     for field, value in query_params.items():
#         if field in ['authors', 'keywords']:
#             values = parse_comma_separated_values(value)
#             query[mapping.get(field, field)] = {'$in': values}
#         else:
#             if fuzzy:
#                 query[mapping.get(field, field)] = {
#                     '$regex': re.escape(value), '$options': 'i'}
#             else:
#                 query[mapping.get(field, field)] = {
#                     '$regex': re.escape(value), '$options': 'i'}
#     return query

# Enhanced fuzzy match function


def fuzzy_match(query_value, data_value, threshold=55):
    # print("Query Value: ", query_value)
    # print(fuzz.ratio(query_value.lower(), data_value.lower()))
    return fuzz.ratio(query_value.lower(), data_value.lower()) >= threshold

# Search MongoDB with fuzzy matching


def search_documents(query, db, mapping, fuzzy=False):
    collection = db['IEEE'] if db == db1 else db['ResearchGate']
    print("Query: ", query)
    result_set = []

    if 'publisher_organization' in query and len(query) == 1:
        source_query = {}
        all_mapped_docs = []
        for doc in collection.find(source_query):
            mapped_doc = {central_key: doc.get(mapping.get(
                central_key, central_key), None) for central_key in central_schema}
            all_mapped_docs.append(mapped_doc)
        print("All Mapped Docs in DOI: ", all_mapped_docs)
        return all_mapped_docs

    elif 'doi' in query:
        # If DOI is provided, directly query the document
        doi = query['doi']
        # print("DOI :::: ", doi)
        # input the correct mapping name of doi
        source_query = {mapping.get('doi', 'doi'): doi}
        doc = collection.find_one(source_query)
        # print("DOC: ", doc)
        scores = []
        if doc:
            mapped_doc = {central_key: doc.get(mapping.get(
                central_key, central_key), None) for central_key in central_schema}
            scores.append({
            "entity": mapped_doc,
            "total_score": 100,
            # "match_details": match_details
            })
            print("Executed01")
            return scores
        return result_set

    elif 'date' in query:
        # If date is provided, find documents with the same or publishing date > input date
        date = query['date']
        # all entries from mongo db which have date greater than or equal to the input date
        # print("Mapping: ", mapping)
        source_query = {mapping.get('published_date'): {'$gte': date}}
        # print("Source Query: ", source_query)
        all_mapped_docs = []
        for doc in collection.find(source_query):
            mapped_doc = {central_key: doc.get(mapping.get(
                central_key, central_key), None) for central_key in central_schema}
            all_mapped_docs.append(mapped_doc)
        if (len(query) == 2 or (len(query) == 3 and 'refcount' in query)):
            result_docs = []
            for k in all_mapped_docs:
                result_docs.append({
            "entity": k,
            "total_score": 100,
            # "match_details": match_details
            })
            result_set.extend(result_docs)
            return result_set
        matched_entity = entity_matching(query, all_mapped_docs)
        result_set.extend(matched_entity)
        
    elif 'refcount' in query and int(query['refcount'])>0:
        # If ref_count is provided, find documents with the same or higher ref_count
        ref_count = int(query['refcount'])
        source_query = {mapping.get('ref_count'): {'$gte': ref_count}}
        all_mapped_docs = []
        for doc in collection.find(source_query):
            mapped_doc = {central_key: doc.get(mapping.get(
                central_key, central_key), None) for central_key in central_schema}
            all_mapped_docs.append(mapped_doc)
        if (len(query) == 2 or (len(query) == 3 and 'date' in query)):
            result_docs = []
            for k in all_mapped_docs:
                result_docs.append({
            "entity": k,
            "total_score": 100,
            # "match_details": match_details
            })
            result_set.extend(result_docs)
            return result_set
        matched_entity = entity_matching(query, all_mapped_docs)
        result_set.extend(matched_entity)
    else:
        # here find all the entries from mongo db.
        source_query = {}
        all_mapped_docs = []
        for doc in collection.find(source_query):
            mapped_doc = {central_key: doc.get(mapping.get(
                central_key, central_key), None) for central_key in central_schema}
            all_mapped_docs.append(mapped_doc)
        # print("All Mapped Docs: ",all_mapped_docs)
        matched_entity = entity_matching(query, all_mapped_docs)
        result_set.extend(matched_entity)

    return result_set


def preprocess(text):
    # if text is list then join all the elements of list
    if isinstance(text, list):
        return " ".join(text).lower().strip() if text else ""
    return text.lower().strip() if text else ""

def fuzzy_match_score(input_value, target_value):
    return fuzz.partial_ratio(preprocess(input_value), preprocess(target_value))

def semantic_match_score(input_value, target_value):
    # Use Sentence-BERT embeddings to calculate semantic similarity
    # print("Input Value: ", input_value)
    # print("Target Value: ", target_value)
    # if target_value is list then join all the elements of list
    if isinstance(target_value, list):
        target_value = " ".join(target_value)
    embeddings = model.encode([input_value, target_value], convert_to_tensor=True)
    return util.pytorch_cos_sim(embeddings[0], embeddings[1]).item()

def entity_matching(user_entity, db_entities,isSql=False):
    scores = []
    # print("User Entity: ", user_entity)
    for db_entity in db_entities:
        total_score = 0
        match_details = {}

        for attr, user_value in user_entity.items():
            if attr == 'date' or attr == 'publisher_organization' or attr == 'doi' or attr == 'refcount':
                continue

            # print("User Value: ", user_value)
            # print("attr: ", attr)
            if user_value:
                # print("matching attribute: ", attr)
                db_value = db_entity.get(attr, "")

                if attr == 'authors':
                    if isSql:
                        db_value = db_value.split(",")
                    for value1 in user_value.split(","):
                        for value2 in db_value:
                            # print("Value2: ", value2, "User Value: ", value1)
                            fuzzy_score = fuzzy_match_score(value1, value2)
                            semantic_score=0
                            # semantic_score = semantic_match_score(value1, value2)
                            # Combine the scores (weighted sum)
                            combined_score = 0.7 * fuzzy_score + (0.3 * semantic_score * 100)
                            total_score += combined_score
                
                elif attr == 'keywords':
                    if isSql:
                        db_value = db_value.split(",")
                    for value1 in user_value.split(","):
                        for value2 in db_value:
                            # print("Value2: ", value2, "User Value: ", value1)
                            fuzzy_score = fuzzy_match_score(value1, value2)
                            # semantic_score=0
                            semantic_score = semantic_match_score(value1, value2)
                            # Combine the scores (weighted sum)
                            combined_score = 0.2 * fuzzy_score + (0.8 * semantic_score * 100)
                            total_score += combined_score

                else:
                    # Calculate fuzzy and semantic match scores
                    fuzzy_score = fuzzy_match_score(user_value, db_value)
                    semantic_score = semantic_match_score(user_value, db_value)
                    # Combine the scores (weighted sum)
                    combined_score = 0.5 * fuzzy_score + (0.5 * semantic_score * 100)
                    total_score += combined_score
            
                # match_details[attr] = {
                #     "user_value": user_value,
                #     "db_value": db_value,
                #     "fuzzy_score": fuzzy_score,
                #     "semantic_score": semantic_score,
                #     "combined_score": combined_score
                # }

        # Store the total score for this entity
        scores.append({
            "entity": db_entity,
            "total_score": total_score,
            # "match_details": match_details
        })
        # print("Matched Results : ",scores[-1])
    
    # Sort by highest score
    scores = sorted(scores, key=lambda x: x["total_score"], reverse=True)
    # extract entities with score > max_score/2
    # max_score = scores[0]["total_score"]
    # scores = [score for score in scores if score["total_score"] > max_score/1.5]
    # # for score in scores:
    # #     print("Matched Results : ",score)
    # matched_entity = [score["entity"] for score in scores]
    return scores


# def entity_matching(query, mapped_doc, isSql=False):
#     matched_entity = []
#     query_str = ""
#     # print("Query in entity_matching: ", query)
#     # here concateneate all input values in one string separted by ';' & author names in sorted order.
#     for key, value in sorted(query.items()):
#         if (key == 'authors'):
#             query_str += ";".join([author.strip()
#                                   for author in sorted(value.split(","))]).strip() + ";"
#             print("Value: ", value)
#         elif (key == 'keywords'):
#             query_str += ";".join([keyword.strip()
#                                   for keyword in sorted(value.split(","))]).strip() + ";"
#         # if date is present then ignore it
#         elif (key == 'date'):
#             continue
#         else:
#             query_str += value+";"
#     # print("Query String 1: ", query_str)

#     # print("Mapped Doc: ",mapped_doc)
#     for entity in mapped_doc:
#         entity_str = ""
#         # print("Entity: ", entity)
#         for key, value in sorted(entity.items()):
#             # ignore all keys which do not have valid mapping in central schema and also ignore the key 'doi'
#             # ALSO IGNORE THE DATE HERE
#             if (key not in central_schema.keys() or key == 'doi' or key not in query.keys()):
#                 continue
#             if (key == 'date'):
#                 continue
#             elif (key == 'authors'):
#                 if (isSql):
#                     # first convert the value string to list using ast.literal_eval
#                     import ast
#                     value = ast.literal_eval(value)
#                     entity_str += ";".join(sorted(value)).strip() + ";"
#                 else:
#                     entity_str += ";".join(sorted(value)).strip() + ";"
#             elif (key == 'keywords'):
#                 if (isSql):
#                     import ast
#                     value = ast.literal_eval(value)
#                     entity_str += ";".join(sorted(value)).strip() + ";"
#                 else:
#                     entity_str += ";".join(sorted(value)).strip() + ";"
#             else:
#                 entity_str += str(value)+";"
#         # print("Entity String 1: ", entity_str)
#         is_matched = fuzzy_match(query_str, entity_str)
#         if (is_matched):
#             matched_entity.append(entity)

#     return matched_entity

#     # source_query = build_query(query, mapping, fuzzy)

#     # for doc in collection.find(source_query):
#     #     # Fuzzy match additional fields if needed
#     #     for field, value in query.items():
#     #         if field in doc:
#     #             if fuzzy and not fuzzy_match(value, str(doc[field])):
#     #                 continue
#     #     mapped_doc = {central_key: doc.get(mapping.get(
#     #         central_key, central_key), None) for central_key in central_schema}
#     #     result_set.append(mapped_doc)
#     return result_set

# Search MySQL documents with fuzzy matching


def search_mysql_documents(query, cursor, table_name, mapping):
    # Build WHERE clause
    conditions = []
    if 'publisher_organization' in query and len(query) == 1:
        # fetch all the entries from mysql
        sql_query = f"SELECT * FROM {table_name}"
        params = []
        result_set = []
        cursor.execute(sql_query, params)
        all_mapped_docs = []
        for row in cursor.fetchall():
            mapped_doc = {central_key: row.get(mapping.get(
                central_key, central_key), None) for central_key in central_schema}
            all_mapped_docs.append(mapped_doc)
        return all_mapped_docs

    elif 'doi' in query:
        conditions.append(f"{mapping.get('doi', 'doi')} = %s")
        params = [query['doi']]
        sql_query = f"SELECT * FROM {table_name} WHERE {conditions[0]}"
        cursor.execute(sql_query, params)
        result_set = []
        scores = []
        for row in cursor.fetchall():
            mapped_doc = {central_key: row.get(mapping.get(
                central_key, central_key), None) for central_key in central_schema}
            scores.append({
            "entity": mapped_doc,
            "total_score": 100,
            # "match_details": match_details
            })
            print("Executed001")
            return scores
        return result_set
    
    elif 'date' in query:
        conditions.append(f"{mapping.get('published_date')} >= %s")
        params = [query['date']]
        sql_query = f"SELECT * FROM {table_name} WHERE {conditions[0]}"
        cursor.execute(sql_query, params)
        all_mapped_docs = []
        result_set = []
        for row in cursor.fetchall():
            mapped_doc = {central_key: row.get(mapping.get(
                central_key, central_key), None) for central_key in central_schema}
            all_mapped_docs.append(mapped_doc)
        if (len(query) == 2 or (len(query) == 3 and 'refcount' in query)):
            result_docs = []
            for k in all_mapped_docs:
                result_docs.append({
            "entity": k,
            "total_score": 100,
            # "match_details": match_details
            })
            result_set.extend(result_docs)
            return result_set
        matched_entity = entity_matching(query, all_mapped_docs, True)
        result_set.extend(matched_entity)
        return result_set
    
    elif 'refcount' in query and int(query['refcount'])>0:
        conditions.append(f"{mapping.get('ref_count')} >= %s")
        params = [query['refcount']]
        sql_query = f"SELECT * FROM {table_name} WHERE {conditions[0]}"
        cursor.execute(sql_query, params)
        all_mapped_docs = []
        result_set = []
        for row in cursor.fetchall():
            mapped_doc = {central_key: row.get(mapping.get(
                central_key, central_key), None) for central_key in central_schema}
            all_mapped_docs.append(mapped_doc)
        if (len(query) == 2 or (len(query) == 3 and 'date' in query)):
            result_docs = []
            for k in all_mapped_docs:
                result_docs.append({
            "entity": k,
            "total_score": 100,
            # "match_details": match_details
            })
            result_set.extend(result_docs)
            return result_set
        matched_entity = entity_matching(query, all_mapped_docs, True)
        result_set.extend(matched_entity)
        return result_set
    else:
        # fetch all the entries from mysql
        sql_query = f"SELECT * FROM {table_name}"
        params = []
        result_set = []
        cursor.execute(sql_query, params)
        all_mapped_docs = []
        for row in cursor.fetchall():
            mapped_doc = {central_key: row.get(mapping.get(
                central_key, central_key), None) for central_key in central_schema}
            all_mapped_docs.append(mapped_doc)
        # print("All Mapped Docs SQL: ",all_mapped_docs)
        # print("Query SQL: ", query)
        matched_entity = entity_matching(query, all_mapped_docs, True)
        result_set.extend(matched_entity)
        return result_set




def search2(query):
    global mappings
    global schemas
    global mysql_cursor
    global mysql_table_name
    global central_schema
    global db1
    global db2
    global client1
    global client2
    global similarity_df
    global similarity_df_mysql
    global mysql_conn

    schemas.clear()
    schemas = {
        'schema1': extract_schema(db1['IEEE']),
        'schema2': extract_schema(db2['ResearchGate'])
    }
    # print("Old mappings: ", mappings)
    mappings.clear()
    # print("New mappings: ", mappings)
    # print("Mapping in search: ",mappings)
    for schema_name, schema in schemas.items():
        similarity_df = compute_similarity(
            list(central_schema.keys()), list(schema.keys()))
        mappings[schema_name] = get_best_matches(similarity_df)
    # mysql_conn = mysql.connector.connect(**mysql_config)
    # mysql_cursor = mysql_conn.cursor(dictionary=True)
    schemas['schema3'] = extract_mysql_schema(
        mysql_cursor, mysql_table_name)
    # Generate schema mappings for MySQL
    similarity_df_mysql = compute_similarity(
        list(central_schema.keys()), list(schemas['schema3'].keys()))
    mappings['schema3'] = get_best_matches(similarity_df_mysql)
    # print("New mappings2 : ", mappings)
    # query = {key: request.form[key]
    #          for key in request.form if request.form[key]}
    dbs = [(db1, mappings['schema1']), (db2, mappings['schema2']),
           ('mysql', mappings['schema3'])]
    if 'publisher_organization' not in query:
        query['publisher_organization'] = 'All'
        
    results = []
    print("Query: ", query)
    # print("Mapping: ", mappings)
    if 'publisher_organization' in query:
        if query['publisher_organization'] == 'IEEE':
            results.extend(search_documents(
                query, db1, mappings['schema1'], fuzzy=True))
        elif query['publisher_organization'] == 'ResearchGate':
            results.extend(search_documents(
                query, db2, mappings['schema2'], fuzzy=True))
        elif query['publisher_organization'] == 'CVPR':
            results.extend(search_mysql_documents(
                query, mysql_cursor, mysql_table_name, mappings['schema3']))
        else:
            for db, mapping in dbs:
                if db == 'mysql':
                    results.extend(search_mysql_documents(
                        query, mysql_cursor, mysql_table_name, mapping))
                else:
                    results.extend(search_documents(
                        query, db, mapping, fuzzy=True))
    print("Executed11")
    results = sorted(results, key=lambda x: x["total_score"], reverse=True)
    print("Executed12")
    if len(results) == 0:
        max_score = 0
    else:
        max_score = results[0]["total_score"]
        scores = [score for score in results if score["total_score"] > max_score/1.2]
        print("Scores: ", scores)
        results = [score["entity"] for score in scores]
    # Aggregation (remove duplicates based on DOI)
    print("Executed")
    aggregated_results = {}
    for doc in results:
        doi = doc.get("doi")
        if doi not in aggregated_results:
            aggregated_results[doi] = doc
            # print("SQL PP EE ", aggregated_results[doi]['keywords'])
            # print("Length: ", len(aggregated_results[doi]['keywords']))
            if type(aggregated_results[doi]['keywords']) == str:
                # print("SQL PP EE ",
                #       aggregated_results[doi]['keywords'].split(","))
                aggregated_results[doi]['keywords'] = aggregated_results[doi]['keywords'].split(
                    ",")
    # print("Aggregated Results: ", aggregated_results)
    # print(list(aggregated_results.values()))
    return aggregated_results



# Flask routes


@app.route('/', methods=['GET', 'POST'])
def search():
    global mappings
    global schemas
    global mysql_cursor
    global mysql_table_name
    global central_schema
    global db1
    global db2
    global client1
    global client2
    global similarity_df
    global similarity_df_mysql
    global mysql_conn

    if request.method == 'POST':
        # close old connections
        # client1.close()
        # client2.close()
        # mysql_cursor.close()
        # mysql_conn.close()

        #     client1 = MongoClient(
        # "mongodb+srv://shubham21099:OoaZmPV3SHKCTFF8@rpms-1.upidh.mongodb.net/?retryWrites=true&w=majority&appName=RPMS-1")
        #     client2 = MongoClient(
        # "mongodb+srv://parveen21079:IqOtVWtlL07iko7b@rpms-3.sfebr.mongodb.net/?retryWrites=true&w=majority&appName=RPMS-3")
        #     db1 = client1['RPMS-1']
        #     db2 = client2['RPMS-3']

        schemas.clear()

        schemas = {
            'schema1': extract_schema(db1['IEEE']),
            'schema2': extract_schema(db2['ResearchGate'])
        }

        # print("Old mappings: ", mappings)
        mappings.clear()
        # print("New mappings: ", mappings)
        # print("Mapping in search: ",mappings)
        for schema_name, schema in schemas.items():
            similarity_df = compute_similarity(
                list(central_schema.keys()), list(schema.keys()))
            mappings[schema_name] = get_best_matches(similarity_df)

        # mysql_conn = mysql.connector.connect(**mysql_config)
        # mysql_cursor = mysql_conn.cursor(dictionary=True)

        schemas['schema3'] = extract_mysql_schema(
            mysql_cursor, mysql_table_name)

        # Generate schema mappings for MySQL
        similarity_df_mysql = compute_similarity(
            list(central_schema.keys()), list(schemas['schema3'].keys()))
        mappings['schema3'] = get_best_matches(similarity_df_mysql)

        # print("New mappings2 : ", mappings)

        query = {key: request.form[key]
                 for key in request.form if request.form[key]}
        dbs = [(db1, mappings['schema1']), (db2, mappings['schema2']),
               ('mysql', mappings['schema3'])]
        results = []
        print("Query: ", query)
        # print("Mapping: ", mappings)
        if 'publisher_organization' in query:
            if query['publisher_organization'] == 'IEEE':
                results.extend(search_documents(
                    query, db1, mappings['schema1'], fuzzy=True))
            elif query['publisher_organization'] == 'ResearchGate':
                results.extend(search_documents(
                    query, db2, mappings['schema2'], fuzzy=True))
            elif query['publisher_organization'] == 'CVPR':
                results.extend(search_mysql_documents(
                    query, mysql_cursor, mysql_table_name, mappings['schema3']))
            else:
                for db, mapping in dbs:
                    if db == 'mysql':
                        results.extend(search_mysql_documents(
                            query, mysql_cursor, mysql_table_name, mapping))
                    else:
                        results.extend(search_documents(
                            query, db, mapping, fuzzy=True))
        results = sorted(results, key=lambda x: x["total_score"], reverse=True)
        
        if len(results) == 0:
            max_score = 0
        else:
            max_score = results[0]["total_score"]
            scores = [score for score in results if score["total_score"] > max_score/1.2]
            print("Scores: ", scores)
            results = [score["entity"] for score in scores]

        # Aggregation (remove duplicates based on DOI)
        aggregated_results = {}
        for doc in results:
            doi = doc.get("doi")
            if doi not in aggregated_results:
                aggregated_results[doi] = doc
                # print("SQL PP EE ", aggregated_results[doi]['keywords'])
                # print("Length: ", len(aggregated_results[doi]['keywords']))
                if type(aggregated_results[doi]['keywords']) == str:
                    # print("SQL PP EE ",
                    #       aggregated_results[doi]['keywords'].split(","))
                    aggregated_results[doi]['keywords'] = aggregated_results[doi]['keywords'].split(
                        ",")

        # print("Aggregated Results: ", aggregated_results)
        # print(list(aggregated_results.values()))
        return render_template('results.html', results=list(aggregated_results.values()))
    return render_template('search.html')


co = cohere.ClientV2("v2UznKS7Xf9dywvVWPIy76mIyBkCjIYMYPiMCTlu")
messages=[]
initialize_model= False
initial_input="Hello"
with open("initial_input.txt", "r") as f:
    initial_input = f.read()

# print("Initial Input: ", initial_input)

if not initialize_model:
    # messages.insert(0, {"role": "user", "content": initial_input})
    messages.append({"role": "user", "content": initial_input})
    response = co.chat(
                model="command-r-plus-08-2024",
                messages=messages
    )
    # messages.insert(0, {"role": "assistant", "content": response.message.content[0].text})
    messages.append({"role": "assistant", "content": response.message.content[0].text})
    initialize_model=True

to_be_displayed={}

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if request.method == 'POST':
        # Get user input from the form
        user_input = request.form.get('user_input', '')
        
        try:
            # Generate response using Cohere
            # messages.insert(0, {"role": "user", "content": user_input})
            messages.append({"role": "user", "content": user_input})
            response = co.chat(
                model="command-r-plus-08-2024",
                messages=messages
            )
            # messages.insert(0, {"role": "assistant", "content": response.message.content[0].text})
            messages.append({"role": "assistant", "content": response.message.content[0].text})
            # Extract the response text
            bot_response = response.message.content[0].text
            # now here extract the dictionary from the response similar to Task 1: {central_schema}
            initial_index=bot_response.find("{")
            final_index=bot_response.find("}")
            # check if initial_index and final_index are not -1
            if initial_index!=-1 and final_index!=-1:
                response_dict=bot_response[initial_index:final_index+1]
                response_dict=ast.literal_eval(response_dict)
                print("Response Dict before IF: ", response_dict)

                # STRIP SPACES IF NECESSARY
                # if 'keywords' in response_dict:
                #     response_dict['keywords'] = response_dict['keywords'].split(",")
                # if 'authors' in response_dict:
                #     response_dict['authors'] = response_dict['authors'].split(",")
                
                aggregated_results = search2(response_dict)
                # in new tab open the search page and display the results
                to_be_displayed = aggregated_results
                session['aggregated_results'] = to_be_displayed
                print("To be displayed: ",to_be_displayed)
                return render_template('chat.html', user_input=user_input, bot_response=bot_response, results=session['aggregated_results'])
                print("Response Dict After IF: ", response_dict)
            # print("Messages: ", messages)
            # Return the response
            return render_template('chat.html', user_input=user_input, bot_response=bot_response)
        
        except Exception as e:
            # Handle any errors
            error_message = f"An error occurred: {str(e)}"
            return render_template('chat.html', error=error_message)
    
    # GET request - render the initial page
    return render_template('chat.html')


app.config["SESSION_TYPE"] = "filesystem"
Session(app)

@app.route('/results')
def results():
    # Fetch results (you can pass this dynamically instead of storing globally)
    to_be_displayed = session.get('aggregated_results', [])
    print("Results FINAL : ", to_be_displayed)
    print("Executed2")
    return render_template('results.html', results=list(to_be_displayed.values()))



# Run Flask app
if __name__ == '__main__':
    app.run(debug=True)


# {"_id":{"$oid":"6740924eca481a2e1bcf1d7d"},"license":"http://www.springer.com/tdm","subject":[],"issue":"5","page":"638-640","accepted_date":"2023-10-14","language":"English","research_title":"Magnetic susceptibility of solid solutions","author":["F. A. Sidorenko","L. A. Miroshnikov"],"paper_abstract":"Abstract not provided.","date":"2023-10-18","published_on_date":"2024-06-24","doi_id":"10.1007/bf00814856","Affiliation_org":"Springer Science and Business Media LLC","link":"http://dx.doi.org/10.1007/bf00814856","issn_num":"0038-5697","refCount":{"$numberInt":"5"},"doc_type":"journal-article","vol":"12","creationDate":"2022-06-01","important_keywords":["magnetic","solutions","solid","based"]}
