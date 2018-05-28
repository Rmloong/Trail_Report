from .knn_model import prep_neighbors, dates_in_circle, prep_for_knn, make_forest
from .merge_weather import get_weather_data, get_closest_station, merge_weather_trails
import pandas as pd
import numpy as np
import math
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import scale
from sklearn.preprocessing import normalize
import pickle
import boto3
from io import BytesIO


def get_data(hike,date):
    df,df_trail, weather, weather_dist = load_databases()
    hike_df = df_trail.loc[df_trail['hike_name'] == hike]
    date_stamp = pd.to_datetime(date)
    conditions = ['condition|snow', 'condition|trail','condition|bugs','condition|road']
    for condition in conditions:
        hike_df[f'neighbors_average {condition}'] = get_new_neighbors(df,condition,hike,date_stamp)
    hike_df['date'] = date_stamp
    hike_df['month'] = date_stamp.month
    hike_df['year'] = date_stamp.year
    hike_df['last_year']= date_stamp.year -1
    hike_df['date_sin'],hike_df['date_cos'] = dates_in_circle(hike_df['date'])
    get_closest_station(hike_df,weather_dist)
    hike_all_df = merge_weather_trails(weather,hike_df)
    X_test = clean_for_model(hike_all_df)
    return X_test


def load_databases():
    weather, weather_dist = get_weather_data()
    df_init = pd.read_csv('data/WTA_olympics_merged.csv', sep = '|',lineterminator='\n')
    df = df_init.fillna(0)
    df_trail = pd.read_csv('data/WTA_trails_clean_w_medians.csv',lineterminator='\n')
    return df, df_trail, weather, weather_dist


def get_new_neighbors(df,condition,hike,date_stamp):
    """Get's index of closest 20 neighbors in df."""
    neigh = prep_neighbors(df,condition)
    hike_knn_df = df.loc[df['Trail'] == hike][['highest_point','distance_from_median']]
    hike_knn_df['month'] = date_stamp.month
    hike_info = hike_knn_df.iloc[0]
    X = scale(hike_info)
    indx = neigh.kneighbors([X])
    indx_list = list(indx[1][0])
    averages = get_condition_averages(df,indx_list,condition)
    return averages

def get_condition_averages(df,indx_list,condition):
    neighbors = df.iloc[indx_list]
    average = neighbors[condition].mean()
    return average

def clean_for_model(hike_all_df):
    df_clean = hike_all_df.drop(['url','which_pass','super_region',
    'sub_region','closet_station','hike_name','last_year','month','year','date','Unnamed: 0'], axis=1)
    df_full = df_clean.fillna(0)
    return df_full


class TrailPred(object):

    def __init__(self):
        self.models = {}
        self.conditions = ['condition|snow', 'condition|trail','condition|bugs','condition|road']
        self.X_train = pd.read_csv('data/olympics_Xall.csv',sep = '|',lineterminator='\n')
        self.y_all = pd.read_csv('data/olympics_yall.csv',sep = '|',lineterminator='\n')
        self.actual_cols = self.X_train.columns.tolist()

    def prep_train(self,condition):
        y_train = self.y_all[condition]
        return y_train

    def fit(self):
        for condition in self.conditions:
            y_train = self.prep_train(condition)
            self.models[condition]= make_forest(self.X_train,y_train)

    def predict(self,X_test):
        pred = {}
        for condition,model in self.models.items():
            pred[condition]= model.predict_proba(X_test[self.actual_cols])
        return pred

def get_pickle():
    """
    Access pickle of all fit models from public s3 bucket
    **Input parameters**
    ------------------------------------------------------------------------------
    None.
    **Output**
    ------------------------------------------------------------------------------
    tp: dictionary built by class tp. Keys: conditions, values:fit models
    """
    s3 = boto3.resource('s3')
    with BytesIO() as data:
        s3.Bucket("trailreportdata").download_fileobj("tp.pkl", data)
        data.seek(0)    # move back to the beginning after writing
        tp = pickle.load(data)
    return tp

def main_dump():
    tp = TrailPred()
    tp.fit()
    with open('tp.pkl','wb') as f:
        pickle.dump(tp,f)

def main_pred():
    hike = 'Mount Rose'
    date = '05/22/18'
    X_test = get_data(hike,date)
    # with open('tp.pkl','rb') as f:
    #     tp = pickle.load(f)
    tp = get_pickle()
    pred = tp.predict(X_test)
    print(pred)
if __name__ == '__main__':
    main_pred()
