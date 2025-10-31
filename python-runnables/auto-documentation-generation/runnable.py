"""docstring TBD"""

# This file is the actual code for the Python runnable auto-documentation-generation

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


class MyRunnable(Runnable):
    """Base class for Dataiku DSS Macro in a plugin"""

    def __init__(self, project_key, config, plugin_config):
        """
        :param project_key: the project in which the runnable executes
        :param config: the dict of the configuration of the object
        :param plugin_config: contains the plugin settings
        """
        self.project_key = project_key
        self.config = config
        self.plugin_config = plugin_config

        self.__num_ai_services_used = 0
        self.__language                = self.config["language"]
        self.__project_purpose         = self.config["project_purpose"]
        self.__project_length          = self.config["project_length"]
        self.__save_description        = self.config["save_description"]
        self.__tagname_aigen           = self.config["tagname_aigen"]
        self.__tagname_do_not_autofill = self.config["tagname_DoNotAutoFill"]

        self.__autofill_projects  = "projects"  in self.config["object_types_to_autofill"]
        self.__autofill_flowzones = "flowzones" in self.config["object_types_to_autofill"]
        self.__autofill_datasets  = "datasets"  in self.config["object_types_to_autofill"]

        # multi-select
        pf = self.config["project_filter"] # all_projects, project_tags, project_folder

        
        
        
        # self.__projects_list = self.config.get("projects_list", [])

        self.__client = dataiku.api_client()
        self.__projects_list = self.client.list_project_keys()

    @property
    def num_ai_services_used(self):
        """Returns the total number of AI services used during the auto documentation process.

        Returns:
            int: The count of AI services that were utilized
        """
        return self.__num_ai_services_used

    def get_progress_target(self):
        """
        If the runnable will return some progress info, have this function return a tuple of
        (target, unit) where unit is one of: SIZE, FILES, RECORDS, NONE
        """
        return None

    def run_datasets(self):
        """
        x
        """
        
        if self.__autofill_datasets:
            print("Skipping Datasets since they're not selected")
            return None

        # iterate through projects
        for project_key in self.__projects_list:
            project_handle = self.__client.get_project(project_key)

            # iterate through all datasets in that project
            for dataset in project_handle.list_datasets():
                dataset_id = dataset["name"]
                dataset_handle = project_handle.get_dataset(dataset_id)

                if not dataset_handle.exists():
                    print(
                        f"[SKIP] dataset does not exist:   {project_key} - {dataset_id}"
                    )
                    continue

                # check if there is no schema
                if len(dataset["schema"].get("columns", "")) == 0:
                    print(
                        f"[SKIP] dataset has empty schema: {project_key} - {dataset_id}"
                    )
                    continue

                # skip this dataset if it already has all of the description fields filled out
                if not dataset_has_full_documentation(project_handle, dataset_id):

                    # test if the first row can be read. VERY IMPORTANT to filter out a lot of
                    # wasted AI Services calls.
                    if not read_first_dataset_row(project_key, dataset_id):
                        print(
                            f"[SKIP] dataset could not be read: {project_key} - {dataset_id}"
                        )
                        continue

                    print(
                        f"Auto-generating documentation for {project_key}'s dataset: {dataset_id} ..."
                    )
                    try:
                        # always increment this BEFORE calling generate_ai_description since
                        # generate_ai_description often raises an exception
                        self.__num_ai_services_used += 1

                        # this blocks execution, doesn't utilize Futures/JobID system
                        # actually generate and save the description
                        _ = dataset_handle.generate_ai_description(
                            language=self.__language,
                            save_description=self.__save_description,
                        )

                    #                 if SAVE_DESCRIPTION and dataset_has_full_documentation(project_handle, dataset_id):
                    #                     print(f"Successfully filled out all fields for {dataset_id}")
                    #                 else:
                    #                     print(f"Attempted to fill in description for dataset, but failed to take effect: {dataset_id}")
                    #                     print(x)

                    except DataikuException as e:
                        # there are so many different types of exceptions that occur
                        # java.lang.IllegalArgumentException: Column not found in schema:
                        print(
                            f"[ERROR] Exception {e} when autofilling: {project_key} - {dataset_id}"
                        )
                        continue

    def run_flowzones(self):
        """
        Iterates through projects and their flow zones to generate AI descriptions where needed.

        This method processes each project in the projects list, examining their flow zones.
        For each flow zone that meets the criteria (non-empty and lacking a description),
        it triggers AI-powered description generation.

        Parameters:
            None

        Returns:
            None

        Side Effects:
            - Updates flow zone descriptions in Dataiku projects
            - Increments self.__num_ai_services_used counter
            - Prints status messages to console

        Raises:
            DataikuException: If there's an error accessing project data or generating descriptions
            json.JSONDecodeError: If there's an error parsing flow zone settings
        """
        if self.__autofill_flowzones:
            print("Skipping Flowzones since they're not selected")
            return None
        
        # Iterate through the list of projects
        for project_key in self.__projects_list:
            project_handle = self.__client.get_project(project_key)
            flow_handle = project_handle.get_flow()

            # Iterate through each flow zone in a specific project
            for flow_zone_handle in flow_handle.list_zones():
                try:
                    # Ensure that the flow zone meets the requirements for
                    # AI-Gen descriptions before attempting to have AI
                    # generate the description.
                    if is_flowzone_empty(flow_zone_handle):
                        print(
                            f"[SKIP] Flow zone must have dataset or recipe in it to autogenerate description: {project_key} - {flow_zone_name}"
                        )
                        continue

                    # get the settings and name of the flow zone
                    flow_zone_settings = flow_zone_handle.get_settings().get_raw()
                    flow_zone_name = flow_zone_settings.get("name", "")

                    # only have AI write the description if there is not one there already
                    if not flow_zone_has_description(flow_zone_handle):
                        print(
                            f"[CREATE] Generating flow zone documentation for {project_key} - {flow_zone_name}"
                        )
                        self.__num_ai_services_used += 1
                        flow_zone_handle.generate_ai_description(
                            language=self.__language,
                            purpose=self.__flowzone_purpose,
                            length=self.__flowzone_length,
                            save_description=self.__save_description,
                        )
                #             else:
                #                 print(f"[SKIP] Flow zone already has a description: {project_key} - {flow_zone_name}")
                except (DataikuException, json.JSONDecodeError):
                    print(
                        f"[ERROR] Creating flow zone description for {project_key} - {flow_zone_name}"
                    )
                    pretty_print_dict(flow_zone_settings)
                    continue

    def run_projects(self):
        """
        x
        """
        if self.__autofill_projects:
            print("Skipping Projects since they're not selected")
            return None

        # iterate through the list of projects
        for project_key in self.__projects_list:
            try:
                project_handle = self.__client.get_project(project_key)

                # Ensure that the project meets the requirements for creating
                # AI generated descriptions
                if is_project_empty(project_handle):
                    print(
                        f"[SKIP] Project must have datasets or recipes in flow, can't create description: {project_key}"
                    )
                    continue

                # Only generate descriptions if there is not one already:
                if is_project_description_empty(project_handle):
                    print(
                        f"Project {project_key} has an empty description, generating AI description for it."
                    )
                    self.__num_ai_services_used += 1

                    # https://developer.dataiku.com/latest/api-reference/python/projects.html#dataikuapi.dss.project.DSSProject.generate_ai_description
                    project_handle.generate_ai_description(
                        language=self.__language,
                        purpose=self.__project_purpose,
                        length=self.__project_length,
                        save_description=self.__save_description,
                    )

            except json.JSONDecodeError:
                print(
                    f"[JSONDecodeError] Creating project description for {project_key}"
                )
                continue

    def run(self, progress_callback):
        """
        Do stuff here. Can return a string or raise an exception.
        The progress_callback is a function expecting 1 value: current progress
        """
        # raise Exception("unimplemented")
        self.run_datasets()
        self.run_flowzones()
        self.run_projects()
        return None
