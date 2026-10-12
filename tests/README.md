# Regression checks

Run with Python 3.11+ and Qt 6 QtTest/QML installed:

```sh
python3 -m unittest discover -s tests -v
```

Set `QMLTESTRUNNER=/path/to/qt6/qmltestrunner` if Qt 6 is installed elsewhere.
QML checks use the offscreen backend and minimal AngelOS/Quickshell doubles;
they execute the production Registry and its process-exit handlers. Missing
qmltestrunner skips QML checks, so check the summary before claiming a full pass.
Python tests mock downloads and use temporary plugin directories. They do not
modify installed plugins or restart AngelOS.

Before release, also exercise the real settings page: filter Widgets and
Utilities, update a batch with one failed download, and confirm that actions
stay disabled until the queue and pending restart finish. Review both the
settings and TUI on an actual AngelOS session.
