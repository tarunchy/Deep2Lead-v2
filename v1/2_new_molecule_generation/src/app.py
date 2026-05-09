import warnings

from popo import SmileSet, SmileString, SmileRequest
from rdkit.rdBase import BlockLogs

warnings.filterwarnings('ignore')
import os
from rdkit.Chem import rdBase, RDConfig
from rdkit import Chem
from rdkit.Chem import PandasTools
from rdkit.Chem.Draw import IPythonConsole
from rdkit.Chem.Descriptors import qed
from rdkit.Chem import Descriptors

print( rdBase.rdkitVersion )
from rdkit.Chem import AllChem as Chem
from rdkit.Chem import Draw
from rdkit.Chem import AllChem
from rdkit.Chem.Draw import SimilarityMaps
# tensorflow backend
from os import environ
environ['KERAS_BACKEND'] = 'tensorflow'
# import scientific py
import numpy as np
import pandas as pd
# rdkit stuff
from rdkit.Chem import AllChem as Chem
from rdkit.Chem import PandasTools
# plotting stuff
import matplotlib.pyplot as plt
import matplotlib as mpl
from IPython.display import SVG, display

# adding path with code to PATH variable
import sys
sys.path.insert(1, '/Users/user/Documents/BD4H/drug_discovery/2_new_molecule_generation/src')
# vae stuff
from processor.vae_utils import VAEUtils
from processor import mol_utils as mu

from flask import Flask
from flask_cors import CORS
# Instead of using this: from flask_restful import Api
# Use this:

from flask_restful_swagger_2 import Api, swagger, Resource

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

noise=5.0
vae = ''
from rdkit import RDLogger
lg = RDLogger.logger()
lg.setLevel(RDLogger.CRITICAL)

app = Flask(__name__)
CORS(app)
api = Api(app, api_version='0.1')
limiter = Limiter(
    app,
    key_func=get_remote_address
)

from rdkit import Chem
from rdkit.Chem import rdMolDescriptors
import pickle

import math
from collections import defaultdict

import os.path as op


def numBridgeheadsAndSpiro(mol, ri=None):
    nSpiro = rdMolDescriptors.CalcNumSpiroAtoms(mol)
    nBridgehead = rdMolDescriptors.CalcNumBridgeheadAtoms(mol)
    return nBridgehead, nSpiro


def calculateScore(m):
    # fragment score
    fp = rdMolDescriptors.GetMorganFingerprint(m,
                                               2)  # <- 2 is the *radius* of the circular fingerprint
    fps = fp.GetNonzeroElements()
    score1 = 0.
    nf = 0
    for bitId, v in fps.items():
        nf += v
        sfp = bitId
        score1 += v
    score1 /= nf

    # features score
    nAtoms = m.GetNumAtoms()
    nChiralCenters = len(Chem.FindMolChiralCenters(m, includeUnassigned=True))
    ri = m.GetRingInfo()
    nBridgeheads, nSpiro = numBridgeheadsAndSpiro(m, ri)
    nMacrocycles = 0
    for x in ri.AtomRings():
        if len(x) > 8:
            nMacrocycles += 1

    sizePenalty = nAtoms ** 1.005 - nAtoms
    stereoPenalty = math.log10(nChiralCenters + 1)
    spiroPenalty = math.log10(nSpiro + 1)
    bridgePenalty = math.log10(nBridgeheads + 1)
    macrocyclePenalty = 0.
    # ---------------------------------------
    # This differs from the paper, which defines:
    #  macrocyclePenalty = math.log10(nMacrocycles+1)
    # This form generates better results when 2 or more macrocycles are present
    if nMacrocycles > 0:
        macrocyclePenalty = math.log10(2)

    score2 = 0. - sizePenalty - stereoPenalty - spiroPenalty - bridgePenalty - macrocyclePenalty

    # correction for the fingerprint density
    # not in the original publication, added in version 1.1
    # to make highly symmetrical molecules easier to synthetise
    score3 = 0.
    if nAtoms > len(fps):
        score3 = math.log(float(nAtoms) / len(fps)) * .5

    sascore = score1 + score2 + score3

    # need to transform "raw" value into scale between 1 and 10
    min = -4.0
    max = 2.5
    sascore = 11. - (sascore - min + 1) / (max - min) * 9.
    # smooth the 10-end
    if sascore > 8.:
        sascore = 8. + math.log(sascore + 1. - 9.)
    if sascore > 10.:
        sascore = 10.0
    elif sascore < 1.:
        sascore = 1.0

    return sascore


def processMols(mols):
    print('smiles\tName\tsa_score')
    for i, m in enumerate(mols):
        if m is None:
            continue

        s = calculateScore(m)

        smiles = Chem.MolToSmiles(m)
        print(smiles + "\t" + m.GetProp('_Name') + "\t%3f" % s)


def perturb_z(z, seed, noise_norm, constant_norm=False):

    if seed > 0:
        np.random.seed(seed)

    if noise_norm > 0.0:
        noise_vec = np.random.normal(0, 1, size=z.shape)
        noise_vec = noise_vec / np.linalg.norm(noise_vec)
        if constant_norm:
            return z + (noise_norm * noise_vec)
        else:
            noise_amp = np.random.uniform(
                0, noise_norm, size=(z.shape[0], 1))
            return z + (noise_amp * noise_vec)
    else:
        return z



def z_to_smiles(self,
                z,
                decode_attempts=250,
                noise_norm=0.0,
                constant_norm=False,
                early_stop=None,seed=0):
    if not (early_stop is None):
        Z = np.tile(z, (25, 1))
        Z = perturb_z(Z, seed, noise_norm)
        X = self.decode(Z)
        smiles = self.hot_to_smiles(X, strip=True)
        df = self.prep_mol_df(smiles, z)
        if len(df) > 0:
            low_dist = df.iloc[0]['distance']
            if low_dist < early_stop:
                return df

    Z = np.tile(z, (decode_attempts, 1))
    Z = perturb_z(Z,seed, noise_norm)
    print(z)
    X = self.decode(Z)
    print(X.shape)
    smiles = self.hot_to_smiles(X, strip=True)
    # df = self.prep_mol_df(smiles, z)
    df = pd.DataFrame({'smiles': smiles})
    # print(df.head(5))
    return df

# Use the swagger Api class as you would use the flask restful class.
# It supports several (optional) parameters, these are the defaults:
from popo import *

known_users = []

from flask import request


class SmileResource(Resource):
    decorators = [limiter.limit('10/minute')]
    @swagger.doc({
        'tags': ['Smile'],
        'description': 'Predict a Smile String',
        'parameters': [
            {
                'name': 'body',
                'description': 'Request body',
                'in': 'body',
                'schema': SmileRequest,
                'required': True,
            }
        ],
        'responses': {
            '200': {
                'description': 'Predicted Smile String',
                'schema': SmileString,
                'headers': {
                    'Location': {
                        'type': 'string',
                        'description': 'Location of the new item'
                    }
                },
                'examples': {
                    'application/json': {
                        'smile': 'C1CNP(=O)(OC1)N(CCCl)CCCl'
                    }
                }
            }
        }
    })
    def post(self):
        """
        Predict a Smile String
        """
        # Validate request body with schema model
        new_smile = ''
        print(request.get_json())
        data = SmileRequest(**request.get_json())
        try:
            noise = float(data['noise'])
        except ValueError as e:
            noise = 0.0

        print("Predicting new Drug....", data['smile'], " Noise:", data['noise'])
        original_smile = str(data['smile'] + '')
        smiles_1 = mu.canon_smiles(str(data['smile'] + ''))
        print('cannonical Smike', smiles_1)

        i = 1
        while i < 100:
            try:
                i = i + 1
                X_1 = vae.smiles_to_hot(smiles_1, canonize_smiles=True)
                print('After X_1')
                z_1 = vae.encode(X_1)
                z_1 = z_1 + noise
                print('After z_1')
                X_r = vae.decode(z_1)
                print('After X_r')
                new_smile = vae.hot_to_smiles(X_r, strip=True)[0]
                print('After new_smile', new_smile)
                mol = Chem.MolFromSmiles(new_smile)
                qed1 = str(qed(mol))
                print(qed1)
                logp = str(Descriptors.MolLogP(mol))
                sas = str(calculateScore(mol))
                print(sas)
                i_mol = Chem.MolFromSmiles(smiles_1)
                i_sas = str(calculateScore(i_mol))
                i_qed = str(qed(i_mol))
                i_logp = str(Descriptors.MolLogP(i_mol))

                print(new_smile)
                break

            except ValueError as e:
                print('Error:', e.args[0])
                if i > 25 :
                    return SmileString(**{"smile": new_smile, "qed": '', "sas": '', "logp": '',"i_smile": new_smile, "i_qed": '', "i_sas": '', "i_logp": ''}), 200


        return SmileString(**{"smile":new_smile,"qed":qed1,"sas":sas,"logp":logp,"i_smile":original_smile + '',"i_qed":i_qed,"i_sas":i_sas,"i_logp":i_logp}), 200


class SmileSetResource(Resource):
    decorators = [limiter.limit('10/minute')]
    @swagger.doc({
        'tags': ['Smile'],
        'description': 'Predict a List of random Smile String',
        'responses': {
            '201': {
                'description': 'A Set of Random Smile Strings',
                'schema': SmileSet,
                'examples': {
                    'application/json': {
                        'smile': '{"randomSmiles": ["C1CNP(=O)(OC1)N(CCCl)CCCl", "NC(=O)NC(C)c1ccsc(C)cccc1COc1ccc1" ]}'
                    }
                }
            }
        }
    })
    def get(self):

        smile_set = set()
        noise = 5.0
        i = 1
        print("Generating valid Random Molecule...")
        iteration = 500
        while i <= iteration:

            try:
                z_1 = np.random.normal(size=(1, 196))
                temp1 = vae.decode(z_1)
                #df = vae.z_to_smiles(z_1, decode_attempts=100, noise_norm=noise)
                #temp_set = set(df['smiles'])

                reconstructed_smiles_1 = vae.hot_to_smiles(temp1, strip=True)[0]
                block = BlockLogs()

                mol = Chem.MolFromSmiles(reconstructed_smiles_1)
                if mol:
                    print(len(reconstructed_smiles_1))
                    if len(reconstructed_smiles_1) > 10:
                        smile_set.add(reconstructed_smiles_1)
                    if len(smile_set) > 5:
                        break

            except Exception as e:
                print('Iteration:',i,' - Error:',str(e))
                i += 1
                continue

            i += 1

        del block
        print("Generated ",len(smile_set)," random molecule")
        uniqueMoleculeCount = len(smile_set)
        return SmileSet(**{"uniqueMoleculeCount":uniqueMoleculeCount,"randomSmiles":list(smile_set)}), 200



class SmileSetResourceV2(Resource):
    decorators = [limiter.limit('10/minute')]
    @swagger.doc({
        'tags': ['Smile'],
        'description': 'Predict a Smile String based on a input',
        'parameters': [
            {
                'name': 'body',
                'description': 'Request body',
                'in': 'body',
                'schema': SmileRequest,
                'required': True,
            }
        ],
        'responses': {
            '200': {
                'description': 'A Set of Random Smile Strings',
                'schema': SmileSet,
                'examples': {
                    'application/json': {
                        'smile': '{"randomSmiles": ["C1CNP(=O)(OC1)N(CCCl)CCCl", "NC(=O)NC(C)c1ccsc(C)cccc1COc1ccc1" ]}'
                    }
                }
            }
        }
    })
    def post(self):

        print("Generating valid Random Molecule...")

        #print(request.get_json())
        data = SmileRequest(**request.get_json())

        seed_value = int(data['seed'])
        noise = float(data['noise'])

        #print(request.get_json())
        smiles_1 = mu.canon_smiles(data['smile'])
        #print(type(data['noise']), data['noise'],"  ", data['attempts'],type(data['attempts']))
        try:
            if noise > 10.0 :
                noise = 10.0
            else:
                if noise < 0.0:
                    noise = 1.0
            attempts = int(data['attempts'])
            if attempts > 1000 :
                attempts = 1000
            else:
               if attempts < 0 :
                   attempts = 1

        except Exception as e:
                print('Error:',str(e))
                noise = 5.0
                attempts = 10

        #print(smiles_1)
        #noise = data['noise']
        X_1 = vae.smiles_to_hot(smiles_1, canonize_smiles=True)
        z_1 = vae.encode(X_1)
        #df = z_to_smiles(vae,z_1, decode_attempts=attempts, noise_norm=noise,seed=seed_value)
        df = vae.z_to_smiles(z_1, decode_attempts=attempts, noise_norm=noise)
        #print(df.smiles)
        smile_set = set(df['smiles'])
        uniqueMoleculeCount = len(smile_set)

        print("Generated ",len(smile_set)," random molecule")
        return SmileSet(**{"uniqueMoleculeCount":uniqueMoleculeCount,"randomSmiles":list(smile_set)}), 200




def auth(api_key, endpoint, method):
    # Space for your fancy authentication. Return True if access is granted, otherwise False
    return True


swagger.auth = auth

api.add_resource(SmileResource, '/api/smile')
api.add_resource(SmileSetResource, '/api/random/smiles')
api.add_resource(SmileSetResourceV2, '/api/random/smiles/v2')

@app.route('/')
def index():
    return """<head>
    <meta http-equiv="refresh" content="0; url=http://petstore.swagger.io/?url=http://localhost:5000/api/swagger.json" />
    </head>"""

print('Loading Pre-Trained Model...')
vae = VAEUtils(directory='./model/pre-train/with_property')
print('Model Loaded successfully..')
print("Predicting new Drug in Main")
smiles_1 = mu.canon_smiles('C1CNP(=O)(OC1)N(CCCl)CCCl')
print('cannonical Smike', smiles_1)
X_1 = vae.smiles_to_hot(smiles_1, canonize_smiles=True)
print('After X_1')
z_1 = vae.encode(X_1)
print('After z_1')
X_r = vae.decode(z_1)
print('After X_r')
new_smile = vae.hot_to_smiles(X_r, strip=True)[0]
print('After new_smile', new_smile)

if __name__ == '__main__':
    app.run()

