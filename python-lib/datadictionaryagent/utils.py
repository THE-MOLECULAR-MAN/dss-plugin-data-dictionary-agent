
import json
import sys

# from json import dumps
import traceback

# import pandas as pd
import dataiku
from dataiku.runnables import Runnable
from dataikuapi.utils import DataikuException
import dataikuapi


def is_project_empty(project_handle):
    """This traps the JSONDecodeError exception that occurs when generate_ai_description is called
    if the project has no datasets or recipes or flow zones"""

    # Check if there are any datasets
    has_datasets = len(project_handle.list_datasets()) > 0

    # Check if there are any recipes
    has_recipes = len(project_handle.list_recipes()) > 0

    return (not has_datasets) and (not has_recipes)


def get_dataset_long_description(dataset_handle):
    """
    Retrieves the long description of a dataset from its metadata.

    Args:
        dataset_handle: A handle to the dataset object containing metadata.

    Returns:
        str: The description of the dataset if it exists in metadata, empty string otherwise.
    """
    dataset_metadata = dataset_handle.get_metadata()
    try:
        return dataset_metadata["description"]
    except KeyError:
        return ""


def get_dataset_short_description(dataset_handle):
    """
    Retrieves the short description of a dataset from its settings.

    Args:
        dataset_handle: A DSS dataset handle object that provides access to dataset settings

    Returns:
        str: The short description of the dataset if available, otherwise an empty string

    Example:
        >>> dataset_handle = dataiku.Dataset("my_dataset").get_dataset_handle()
        >>> short_desc = get_dataset_short_description(dataset_handle)
    """
    dataset_settings = dataset_handle.get_settings().get_raw()
    try:
        return dataset_settings["shortDesc"]
    except KeyError:
        return ""


def get_dataset_column_descriptions(dataset_handle):
    """
    Extracts column descriptions from a dataset's schema.

    Args:
        dataset_handle: A DSS dataset handle object containing schema information.

    Returns:
        list: A list of column comments/descriptions from the dataset schema.
              Returns an empty string if 'columns' key is not found in schema.

    Raises:
        KeyError: If schema structure doesn't contain expected 'columns' field.
    """
    dataset_schema = dataset_handle.get_schema()
    try:
        return [item["comment"] for item in dataset_schema["columns"]]
    except KeyError:
        return ""


def dataset_has_any_documentation(project_handle, dataset_id):
    """
    Returns a boolean describing if a specific dataset meets ANY of the following requirements:
        1) It has a shortDesc that is not empty
        2) It has a description that is not empty
        3) ALL columns have descriptions that are not empty.

    Useful for determining if we should auto-generate a description to fill it in.
    """

    # project_handle = client.get_project(project_key)
    dataset_handle = project_handle.get_dataset(dataset_id)

    if get_dataset_short_description(dataset_handle):
        # print(f'Dataset {dataset_id} lacks full documentation because empty: Short Description')
        return True

    if get_dataset_long_description(dataset_handle):
        # print(f'Dataset {dataset_id} lacks full documentation because empty: Long Description')
        return True

    column_descriptions = get_dataset_column_descriptions(dataset_handle)

    if any(s or not s.strip() for s in column_descriptions):
        # print(f'Dataset {dataset_id} lacks full documentation because empty: Column descriptions')
        return True

    # print(f'Dataset {dataset_id} has all description fields filled out.')
    return False

    

def dataset_has_full_documentation(project_handle, dataset_id):
    """
    Returns a boolean describing if a specific dataset meets ALL of the following requirements:
        1) It has a shortDesc that is not empty
        2) It has a description that is not empty
        3) ALL columns have descriptions that are not empty.

    Useful for determining if we should auto-generate a description to fill it in.
    """

    # project_handle = client.get_project(project_key)
    dataset_handle = project_handle.get_dataset(dataset_id)

    if not get_dataset_long_description(dataset_handle):
        # print(f'Dataset {dataset_id} lacks full documentation because empty: Long Description')
        return False

    if not get_dataset_short_description(dataset_handle):
        # print(f'Dataset {dataset_id} lacks full documentation because empty: Short Description')
        return False

    column_descriptions = get_dataset_column_descriptions(dataset_handle)

    if any(not s or not s.strip() for s in column_descriptions):
        # print(f'Dataset {dataset_id} lacks full documentation because empty: Column descriptions')
        return False

    # print(f'Dataset {dataset_id} has all description fields filled out.')
    return True


def is_project_description_empty(project_handle):
    """
    Returns a boolean describing if a specific project an existing description.
    Useful for determining if we should auto-generate a description to fill it in.
    """

    try:
        md = project_handle.get_metadata()
        if not md["description"]:
            return True
    except KeyError:
        return True
    return False


def pretty_print_dict(d):
    """
    Pretty-print a Python dictionary as JSON to standard output.

    This function formats the given object using json.dump(...) with an indentation
    of 4 spaces and keys sorted alphabetically, writing the JSON representation to
    sys.stdout as a side effect.

    Important notes:
    - As implemented, the call is wrapped in print(json.dump(...)). json.dump writes
        the JSON to sys.stdout and returns None, so print will then print "None" after
        the JSON output.
    - The name `sys` must be available (i.e., `import sys` must have been executed
        in the module); otherwise a NameError will be raised.
    - The object `d` must be JSON-serializable; otherwise json.dump will raise a
        TypeError.

    Parameters
    ----------
    d : object
            The Python object to serialize to JSON (typically a dict). Must be JSON-serializable.

    Returns
    -------
    None
            This function has no meaningful return value; it writes output to stdout.

    Raises
    ------
    TypeError
            If `d` contains objects that are not JSON-serializable.
    NameError
            If `sys` is not defined in the current module.

    Examples
    --------
    # Ensure sys is imported in the module where this function is defined:
    pretty_print_dict({'a': 1, 'b': 2})
    # Expected stdout:
    # {
    #     "a": 1,
    #     "b": 2
    # }
    # None  # printed because json.dump(...) returns None and that value is printed
    """
    print(json.dump(d, fp=sys.stdout, indent=4, sort_keys=True))


def flow_zone_has_description(flow_zone_handle):
    """
    Returns a boolean describing if a specific flow zone has an existing description.
    Useful for determining if we should auto-generate a description to fill it in.
    """
    try:
        # the auto-generated ones ONLY CREATE THE LONG DESCRIPTION, don't do the short one.
        flow_zone_settings = flow_zone_handle.get_settings().get_raw()
        flow_zone_description = flow_zone_settings.get("description", "")
        # flow_zone_description_length = len(flow_zone_description)

        # can't use the "not " version, must use len>0 for some reason.
        flow_zone_has_a_nonempty_description = len(flow_zone_description) > 0

        return flow_zone_has_a_nonempty_description
    except json.JSONDecodeError:
        print(f"[ERROR] Trying to get description for {flow_zone_settings['name']}")
        pretty_print_dict(flow_zone_settings)
        return False


def is_flowzone_empty(flowzone_handle):
    """This traps the JSONDecodeError exception that occurs when generate_ai_description is called
    if the flowzone has no datasets or recipes

      There has to be at least one recipe or one dataset in order to explain a zone.

    """
    for i in flowzone_handle.items:
        if type(i) in [
            dataiku.Dataset,
            dataikuapi.dss.recipe.DSSRecipe,
            dataikuapi.dss.dataset.DSSDataset,
        ]:
            return False
    return True


def read_first_dataset_row(project_key, dataset_name):
    """Returns a boolean if the first row of the dataset was readable.
    False implies the dataset was either empty or an exception occurred.
    Useful for determining if autogenerated descriptions of a dataset are possible.
    """
    try:
        dataset_handle = dataiku.Dataset(dataset_name, project_key=project_key)
        df = dataset_handle.get_dataframe(limit=1)

        # Check if the dataframe is empty (no rows)
        if df.empty:
            print("Dataset is empty.")
            return False

        return True

    except Exception:
        # Catch any exception that might occur
        traceback.print_exc()
        return False
