import pandas as pd

# Assuming your DataFrame looks like this
df = pd.DataFrame({
    'satellite': ['Satellite1', 'Satellite2', 'Satellite3'],
    'transmitters': [
        [{'freq': 0.6}, {'freq': 1.5}, {'freq': 2.2}],
        [{'freq': 1.8}, {'freq': 2.5}, {'freq': 3.1}],
        [{'freq': 0.9}, {'freq': 2.3}, {'freq': 3.8}]
    ]
})

import ipdb; ipdb.set_trace()

# Explode the DataFrame
df_exploded = df.explode('transmitters')

# Now, 'transmitters' column is a dictionary. We create a new 'freq' column from it
df_exploded['freq'] = df_exploded['transmitters'].map(lambda x: x['freq'])

# Now you can filter your dataframe using the conditions on the 'freq' column
filtered_df = df_exploded[((df_exploded['freq'] > 0) & (df_exploded['freq'] < 1)) | ((df_exploded['freq'] > 2) & (df_exploded['freq'] < 3))]

# Drop duplicates to get back the original rows (satellites) that meet the condition
#filtered_df = filtered_df.drop_duplicates(subset=['satellite'])

# Reshape the DataFrame back to its original form
filtered_df = filtered_df.groupby('satellite').agg({'transmitters': list}).reset_index()