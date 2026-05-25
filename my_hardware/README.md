# my_hardware

This is a local Physical Agent driver.

The watch process loads this directory, validates `physical_driver.yaml`,
imports `driver.py`, and passes structured `Action` objects into the driver.
The driver does not parse Markdown and does not call the agent runtime.
