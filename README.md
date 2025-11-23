# Dataiku DSS Plugin - Data Dictionary Agent

## Overview

The Dataiku Data Dictionary Agent Plugin is designed provide a chatbot (agent) to help Dataiku users more easily locate a desired dataset to use in a Dataiku Project.

## Features

- **Macro - Fill in empty descriptions**: automaticaly fill in empty descriptions using Dataiku's AI Services to generate descriptions for Projects, Flow Zones, and Datasets.

- **TBD**: agentic capabilities for building a RAG and searching that metadata


## Installation

To install the Dataiku Data Dictionary Agent Plugin, follow these steps:

1. Download the [Source code (zip) from GitHub](https://github.com/THE-MOLECULAR-MAN/dss-plugin-data-dictionary-agent/releases).
2. In your Dataiku instance, navigate Plugins > Add plugin > Upload and select the downloaded plugin package.
3. Follow the on-screen instructions to complete the installation.

## Usage

### Macro Usage

1. **... (Meatball menu) > Macros**: In your Dataiku project, add a new recipe and select the Speech-to-Text plugin.
2. **Automatically generate descriptions for datasets, projects, flowzones**:
   - By default, the macro will not apply changes so you must opt-in to have it fill in empty descriptions
   - Project Filter - You can apply the macro to just the current project, or to all projects you have access to
   - Object types - You can apply automatic descriptions to all of the following object types:
   * Projects - full (long) descriptions as seen on the bottom of the project home page. It does not modify the short description at the top.
	* Flow Zones - Long descriptions are supported, short descriptions are not supported.
	* Datasets
		* short description
		* long description
		* each individual column's description
3. **Run Macro**

Note: 

## Limitations

**Automatically generate descriptions for datasets, projects, flowzones - Macro**
- Dataiku's AI Services only support the above fields at this time and no additional fields. This plugin relies on Dataiku's Python API which has the same limitations, and therefore cannot fill out additional fields like the short description for Flow Zones or Projects.
- [Dataiku's Python API method used to automatically fill in descriptions for datasets, generate_ai_description](https://developer.dataiku.com/latest/api-reference/python/datasets.html#dataikuapi.dss.dataset.DSSDataset.generate_ai_description), only supports replacing ALL of the fields in a dataset. It cannot only fill in soley the descriptions that are empty. In order to avoid replacing human written descriptions with AI written ones, this plugin will not attempt to generate AI descriptions of datasets, projects, or flow zones that have non-empty descriptions. In order for a this macro to run on a dataset, ALL of the description fields must be empty, not just one.


## Support

For any issues or feature requests, please contact the plugin maintainer or open an issue on the [plugin's GitHub repository](https://github.com/THE-MOLECULAR-MAN/dss-plugin-data-dictionary-agent).
