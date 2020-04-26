from flask import Flask, request
import sqlite3
import json

# init dataabase
conn = sqlite3.connect('cmpe273.db')
c = conn.cursor()
c.execute("DROP table tests;")
c.execute("DROP table submissions;")
c.execute("CREATE TABLE tests (test_id INTEGER PRIMARY KEY AUTOINCREMENT,subject TEXT,answer_keys json);")
c.execute("CREATE TABLE submissions (scantron_id INTEGER PRIMARY KEY AUTOINCREMENT, test_id INTEGER, scantron_url text);")
conn.commit()
conn.close()

# EB looks for an 'application' callable by default.
app = Flask(__name__)

@app.route('/api/tests' , methods=['POST'])
def createTests():
  data = request.get_json()
  subject = data['subject']
  answer_keys = data['answer_keys']
  conn = sqlite3.connect('cmpe273.db', check_same_thread=False)
  c = conn.cursor()
  c.execute("INSERT INTO tests(subject, answer_keys) VALUES (?,?)", [subject, json.dumps(answer_keys)])
  test_id = c.lastrowid
  conn.commit()
  conn.close()
  res = {
    "test_id": test_id,
    **data,
    "submissions": []
  }
  return json.dumps(res), 201

@app.route('/api/tests/<test_id>/scantrons' , methods=['POST'])
def uploadAns(test_id):
  # load scantrons
  data = request.get_json()

  # load test
  conn = sqlite3.connect('cmpe273.db', check_same_thread=False)
  c = conn.cursor()
  c.execute("SELECT * FROM tests WHERE test_id =? LIMIT 1;", [test_id])
  row = c.fetchone()
  if row == None:
    return "test not found", 400
  header = [i[0] for i in c.description]
  test = dict(zip(header, row))
  test['answer_keys'] = json.loads(test['answer_keys'])

  # get grading
  result, score = grading(data['answers'], test['answer_keys'])   
  c.execute("INSERT INTO submissions(test_id) VALUES (?)", (test_id))  
  scantron_id = c.lastrowid
  scantron_url = "http://localhost:5000//api/files/{}.json".format(scantron_id)
  res = {
    "scantron_id": scantron_id,
    "scantron_url": scantron_url, 
    "name": data['name'],
    "subject": data['subject'], 
    "score": score,
    "result": result
  }

  # write file
  with open ("files/{}.json".format(scantron_id), "w") as output:
    output.write(json.dumps(res))
  c.execute("UPDATE submissions SET scantron_url= ? WHERE scantron_id= ?;", (scantron_url, scantron_id))
  conn.commit()
  conn.close()
  res = json.dumps(res)
  return res, 201

@app.route('/api/files/<file_name>', methods=['GET'])
def getFile(file_name):
  data = {}
  with open("files/"+file_name) as file:
    data = json.load(file)
  res = json.dumps(data)
  return res, 200

@app.route('/api/tests/<test_id>' , methods=['GET'])
def getTest(test_id):
  conn = sqlite3.connect('cmpe273.db', check_same_thread=False)
  c = conn.cursor()
  c.execute("SELECT * FROM tests WHERE test_id =? LIMIT 1;", [test_id])
  row = c.fetchone()
  if row == None:
    return "test not found", 400
  header = [i[0] for i in c.description]
  res = dict(zip(header, row))
  res['answer_keys'] = json.loads(res['answer_keys'])

  # retrive submssion
  c.execute("SELECT * FROM submissions WHERE test_id =?;", [test_id])
  submission_rows = c.fetchall()
  submission_header = [i[0] for i in c.description]
  submission = list()
  for x in submission_rows:
    with open("files/{}.json".format(x[0])) as file:
      data = json.load(file)
    submission.append(data)
  
  res['submission'] = submission
  res = json.dumps(res)
  conn.close()
  return res, 201


def grading(answers, answer_keys) :
  out = {}
  score = 0
  for (key, val) in answer_keys.items():
    if key in answers:
      if answers[key] == answer_keys[key]:
        score += 2
    out[key] = {
      'actual': answers[key],
      "expected" : answer_keys[key]
    }
  return out, score

# run the app.
if __name__ == "__main__":
    # Setting debug to True enables debug output. This line should be
    # removed before deploying a production app.
    app.debug = True
    app.run()