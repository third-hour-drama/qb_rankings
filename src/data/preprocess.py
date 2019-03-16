"""
preprocess.py

Read in downloaded data and clean for analysis

Data is read from the following sources:
  - Pro Football Reference
  - Football Outsiders
  - Over The Cap
"""

import pandas as pd
import logging
import os
import re
import glob
import click

def import_data(filepath: str):
	"""
	Import data from .csv

	Args:
	  - filepath: Path of file to import

	Returns:
	  - df: Imported DataFrame
	"""
	try:
		df = pd.read_csv(filepath)
	except FileNotFoundError as err:
		logger.exception("{} not found".format(filepath))
		raise err
	else:
		logger.info("Read-in of {} was successful".format(filepath))
		return df


def rmv_chars(row, chars_to_rmv: str, src_column: str) -> str:
	"""
	For a given row remove characters from the value in a 
	specific column in that row

	Args:
	  - row: DataFrame row
	  - chars_to_rmv: String characters to remove from row value
	  - src_column: Column to apply character removal

	Returns:
	  - new_str: string with character removals applied
	"""

	try:
		new_str = re.sub("[{}]".format(chars_to_rmv), "", row[src_column])
	except KeyError as err:
		logger.exception("Column {} passed to rmv_chars not present".format(src_column))
		raise err
	else:
		return new_str


def fix_team_name(row):
	"""
	Remaps team names for teams that moved
	"""
	if row["Tm"] == "STL":
		team = "LAR"
	elif row["Tm"] == "SDG":
		team = "LAC"
	else:
		team = row["Tm"]
	return team


def fix_player_name(row):
	"""
	Remaps player names to [first initial].[last name]

	Args:
	  - row: DataFrame row with Player column

	Returns:
	  - first_initial_last_name: Player name reformated as first initial
								 and last name
	"""

	# split player first and last name into a list
	first_last = row["Player"].split(" ")

	# update first name to first initial
	first_last[0] = first_last[0][0]

	# combine first initial and last name into single string
	first_initial_last_name = "".join(first_last)

	return first_initial_last_name


def calc_qb_wins(row):
	"""
	Calculate QB wins from record. Count ties as 0.5 wins

	Args:
	  - row: DataFrame row with QBrec column

	Returns:
	  - wins: number of wins
	"""
	W_L_T = [float(value) for value in row["QBrec"].split("-")]

	wins = W_L_T[0] + (W_L_T[2]*0.5)

	return wins


def clean_pfr(src_df, year: int):
	"""
	Clean Pro Football Reference data

	Args:
	  - src_df: Raw Pro Football Reference data
	  - year: integer representing year of data being cleaned

	Returns:
	  - df: Cleaned Pro Football Reference data
	"""

	df = src_df.copy()
	logger.info("Dimensions of {} raw PFR DataFrame: {}".format(year, df.shape))
	logger.info("Columns on {} raw PFR DataFrame: {}".format(year, df.columns))

	# add column for year
	df["year"] = year

	# drop interior header rows and restrict to starting QBs
	df = df.loc[(df["Tm"] != "Tm") & (df["Pos"] == "QB")]

	# fix team names for teams that moved
	df["team"] = df.apply(fix_team_name, axis=1)

	# calculate QB wins
	df["qb_wins"] = df.apply(calc_qb_wins, axis=1)

	# remove extra characters so names match across years
	df["Player"] = df.apply(lambda row: rmv_chars(row, "*+", "Player"), axis=1)

	# fix player names to match Football Outsiders format
	df["Player"] = df.apply(fix_player_name, axis = 1)

	# drop unneeded columns
	df = df.drop(["Rk", "Tm", "Pos", "QBrec"], axis=1)

	# Rename columns
	df = df.rename(index=str, columns={
		"Player":"player",
		"4QC":"fourth_qtr_comebacks",
		"ANY/A":"adj_net_yds_per_att",
		"AY/A":"adj_yds_per_att",
		"Age":"age",
		"Att":"att",
		"Cmp":"cmp",
		"Cmp%":"cmp_pct",
		"G":"games",
		"GS":"games_started",
		"GWD":"game_winning_drives",
		"Int":"int",
		"Int%":"int_pct",
		"NY/A":"net_yds_per_att",
		"Rate":"qb_rating",
		"Sk":"sacks",
		"Sk%":"sack_pct",
		"Yds.1":"sack_yds",
		"TD":"td",
		"TD%":"td_pct",
		"Y/A":"yds_per_att",
		"Y/C":"yds_per_cmp",
		"Y/G":"yds_per_game",
		"Yds":"yds"
		})

	# convert columns with numeric data to numeric object type
	df = df.apply(pd.to_numeric, errors="ignore")

	logger.info("Dimensions of cleaned PFR DataFrame: {}".format(df.shape))
	logger.info("Columns on cleaned PFR DataFrame: {}".format(df.columns))

	return df


def clean_fo(src_df, year: int):
	"""
	Clean Football Outsiders data

	Args:
	  - src_df: Raw Football Outsiders data
	  - year: integer representing year of data being cleaned

	Returns:
	  - df: Cleaned Football Outsiders data
	"""

	df = src_df.copy()
	logger.info("Dimensions of {} raw FO DataFrame: {}".format(year, df.shape))
	logger.info("Columns on {} raw FO DataFrame: {}".format(year, df.columns))

	# rename columns
	if list(df.columns)[0] != "Player":
		df.columns = list(df.iloc[0,])
		logger.info("Columns on {} FO DataFrame after rename: {}".format(year, df.columns))
	else:
		logger.info("Columns were not renamed")

	# add column for year
	df["year"] = year

	# remove rows with columns names
	df = df.loc[df["Player"] != "Player"]

	# remove % symbol from DVOA and VOA so values convert to numeric
	df["DVOA"] = df.apply(lambda row: rmv_chars(row, "%", "DVOA"), axis=1)
	df["VOA"] = df.apply(lambda row: rmv_chars(row, "%", "VOA"), axis=1)

	# split DPI into two columns: dpi_count and dpi_yards
	df["dpi_count"] = [value.split("/")[0] for value in df["DPI"]]
	df["dpi_yards"] = [value.split("/")[1] for value in df["DPI"]]
	
	# remove extra characters so names match across years
	df["Player"] = df.apply(lambda row: rmv_chars(row, ".", "Player"), axis=1)

	# Rename columns
	df = df.rename(index=str, columns={
		"Player":"player",
		"Team":"team",
		"EYds":"efctv_yds"
		})

	# limit to columns of interest
	df = df[["player", 
			 "team", 
			 "year", 
			 "DYAR", 
			 "YAR", 
			 "DVOA", 
			 "VOA", 
			 "efctv_yds", 
			 "dpi_count", 
			 "dpi_yards"]]

	# convert columns with numeric data to numeric object type
	df = df.apply(pd.to_numeric, errors="ignore")

	logger.info("Dimensions of cleaned FO DataFrame: {}".format(df.shape))
	logger.info("Columns on cleaned FO DataFrame: {}".format(df.columns))
	
	return df


def clean_otc(src_df, year: int):
	"""
	Clean Over The Cap data

	Args:
	  - src_df: Raw Over The Cap data
	  - year: integer representing year of data being cleaned

	Returns:
	  - df: Cleaned Over The Cap data
	"""

	df = src_df.copy()
	logger.info("Dimensions of {} raw OTC DataFrame: {}".format(year, df.shape))
	logger.info("Columns on {} raw OTC DataFrame: {}".format(year,df.columns))

	# add column for year
	df["year"] = year

	# import team name crosswalk
	xwalk_df = import_data("data/external/team_name_xwalk.csv")

	# merge crosswalk to get standardized team name for later merges
	df = pd.merge(df, xwalk_df, how="left", left_on="Team", right_on="mascot")

	# find a way to print this to log
	team_map = df[["Team", "team"]].drop_duplicates()

	# fix player names to match Football Outsiders format
	df["player"] = df.apply(fix_player_name, axis = 1)

	# remove [$,] symbols from Salary Cap Value for conversion to numeric
	df["salary_cap_value"] = df.apply(lambda row: rmv_chars(row, "$,", "Salary Cap Value"), axis=1)

	# limit to desired columns
	df = df[["player", "team", "year", "salary_cap_value"]]

	# get row with maximum salary within a given player-team-year combo
	df = df.groupby(["player", "team", "year"], as_index=False)["salary_cap_value"].max()

	# convert columns with numeric data to numeric object type
	df = df.apply(pd.to_numeric, errors="ignore")

	logger.info("Dimensions of cleaned OTC DataFrame: {}".format(df.shape))
	logger.info("Columns on cleaned OTC DataFrame: {}".format(df.columns))

	return df


def clean_stack(clean_func, file_pattern: str):
	"""
	Clean yearly files and stack into aggregate file

	Args:
	  - clean_func: Function used to clean specified data
	  - file_pattern: String representing file path pattern to search for 
					  .csv files to import and clean

	Returns:
	  - clean_stack: Stacked DataFrame of all cleaned data for a given
					 file pattern
	"""

	# get list of files to import
	raw_files = glob.glob(file_pattern)

	# Create a list of cleaned DataFrames from the list of raw files
	clean_list = [clean_func(import_data(file), file[-8:-4]) for file in raw_files]
	
	# combine list of DataFrames into a single DataFrame
	clean_stack = pd.concat(clean_list, ignore_index=True)

	return clean_stack


def merge_all(df_list: list):
	"""
	Merge a list of QB-season level DataFrames

	Args:
	  - df_list: List of QB-season level DataFrames to merge

	Returns:
	  - merged_df: Merged DataFrame at the QB-season level
	"""

	for df in df_list:
		logger.info("Dimensions of input DataFrame: {}".format(df.shape))

	# base of merged DataFrame is first DataFrame in the list
	merged_df = df_list[0]

	# merge all DataFrames in the list
	for i in range(1,len(df_list)):
		
		# get DataFrame shape prior to merge
		pre_merge_shape = merged_df.shape
		logger.info("Dimensions of DataFrame after merge {}: {}".format(i, pre_merge_shape))

		# merge iTH DataFrame in list to aggregate DataFrame
		merged_df = pd.merge(merged_df, df_list[i], 
							 how="left", 
							 on=["player", "team", "year"])

		# get DataFrame shape after merge
		post_merge_shape = merged_df.shape
		logger.info("Dimensions of DataFrame after merge {}: {}".format(i, post_merge_shape))

		# verify row count doesn't shape between merges
		try:
			assert(pre_merge_shape[0] == post_merge_shape[0])
		except AssertionError as err:
			logger.exception("Record count changed after merge")
			raise err

	# Reorder columns
	merged_df = merged_df[["player",
			 "team",
			 "year",
			 "age",
			 "games",
			 "games_started",
			 "qb_wins",
			 "att",
			 "cmp",
			 "cmp_pct",
			 "yds",
			 "yds_per_game",
			 "yds_per_att",
			 "yds_per_cmp",
			 "sacks",
			 "sack_yds",
			 "sack_pct", 
			 "dpi_count", 
			 "dpi_yards",
			 "adj_yds_per_att",
			 "net_yds_per_att",
			 "adj_net_yds_per_att",
			 "td",
			 "td_pct",
			 "int",
			 "int_pct",
			 "fourth_qtr_comebacks",
			 "game_winning_drives",
			 "qb_rating",
			 "QBR", 
			 "DYAR", 
			 "YAR", 
			 "DVOA", 
			 "VOA", 
			 "efctv_yds",
			 "salary_cap_value"]]

	# sort DataFrame by player, team, year
	merged_df = merged_df.sort_values(["player", "year", "team"])

	logger.info("Dimensions of final merged DataFrame: {}".format(merged_df.shape))

	return merged_df


def output_analytic(src_df, outfile: str):
	"""
	Output analytic file DataFrame as a .csv file

	Args:
	  - src_df: DataFrame to export

	Returns:
	  - outfile: filepath of exported file
	"""
	try:
		src_df.to_csv(outfile, index=False)
	except FileNotFoundError as err:
		logger.exception("Error saving file {}".format(outfile))
		raise err
	else:
		logger.info("{} created successfully".format(outfile))


@click.command()
@click.argument('outfile', type=click.Path())
def main(outfile):
	"""
	Combine all data into QB-season level analytic file

	Args:
	  - outfile: Name of cleaned analytic file

	Returns: none
	"""

	# import raw data, clean, and stack
	pfr_clean = clean_stack(clean_pfr, "data/raw/qb_season_pfr*.csv")
	fo_clean = clean_stack(clean_fo, "data/raw/qb_season_fo*.csv")
	otc_clean = clean_stack(clean_otc, "data/raw/qb_salary*.csv")

	# merge data, first item in list defines population for merge
	clean_df_list = [pfr_clean, fo_clean, otc_clean]
	merged_df = merge_all(clean_df_list)

	print("Info on final analytic file")
	merged_df.info()

	# output final DataFrame to .csv file
	output_analytic(merged_df, outfile)


if __name__ == "__main__":

	# All directories in program are relative to repo root directory
	# Verify current working directory is repo root directory before proceeding
	try:
		assert os.getcwd().split(os.sep)[-1] == "qb_rankings"
	except AssertionError as err:
		print("Working directory incorrect")
		print("Programs must be run with working directory set to 'qb_rankings'")
		raise err

	# set name of log file
	log_filename = "src/data/preprocess.log"

	# overwite any existing log file
	if os.path.exists(log_filename):
		print("Overwriting log {}".format(log_filename))
		os.remove(log_filename)

	# set up logger
	logging.basicConfig(filename=log_filename,
						filemode="w",
						level=logging.DEBUG,
						format="%(levelname)s: %(asctime)s: %(message)s")

	logger = logging.getLogger(__name__)

	main()