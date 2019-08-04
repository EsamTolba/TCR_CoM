#!/usr/bin/env python
## - Reference-independent approach
"""Import modules"""
from __future__ import print_function
import sys
import os
import argparse
import numpy as np
import Bio.PDB
from Bio.PDB.Chain import Chain
from Bio.PDB.Residue import Residue
from Bio.PDB.Atom import Atom
from Bio.Cluster import pca
from itertools import chain

# from sklearn.decomposition import PCA
# import mdtraj as md

"""Define arguments"""
parser = argparse.ArgumentParser(
    description="TCR-CoM calculates the geometrical parameters (r, theta, phi) of T cell receptors (TCR) on the top of MHC proteins"
)
parser.add_argument("-pdbid", type=str, help="PDB-ID")
parser.add_argument("-mhc_a", type=str, help="ID of MHC alpha chain")
parser.add_argument("-mhc_b", type=str, default=None, help="ID of MHC beta chain")
parser.add_argument("-tcr_a", type=str, help="ID of TCR alpha chain")
parser.add_argument("-tcr_b", type=str, help="ID of TCR beta chain")
parser.add_argument("-output_pdb", type=str, help="Output_PDB_structure")


def add_com_to_pdb(mhci_com, vtcr_com, sample_structure):
    #mhc_com
    mhc_com_chain = 'X'
    sample_structure.add(Chain(mhc_com_chain))
    res_id = (' ', 1, ' ')
    new_residue = Residue(res_id, "MCM", ' ') 
    new_atom = Atom("C", mhci_com, 0, 0.0, ' ', "C", 1, "C")
    new_residue.add(new_atom)
    sample_structure.child_dict[mhc_com_chain].add(new_residue)
    #tcr com
    tcr_com_chain = 'Y'
    sample_structure.add(Chain(tcr_com_chain))
    res_id = (' ', 1, ' ')
    new_residue = Residue(res_id, "TCM", ' ') 
    new_atom = Atom("C", vtcr_com, 0, 0.0, ' ', "C", 1, "C")
    new_residue.add(new_atom)
    sample_structure.child_dict[tcr_com_chain].add(new_residue)
    return sample_structure

"""
Module with assorted geometrical functions on
macromolecules.
"""
# Copyright (C) 2010, Joao Rodrigues (anaryin@gmail.com)
# This code is part of the Biopython distribution and governed by its
# license.  Please see the LICENSE file that should have been included
# as part of this package.
from Bio.PDB import Entity


def center_of_mass(entity, geometric=False):
    """
    Returns gravitic [default] or geometric center of mass of an Entity.
    Geometric assumes all masses are equal (geometric=True)
    """

    # Structure, Model, Chain, Residue
    if isinstance(entity, Entity.Entity):
        atom_list = entity.get_atoms()
    # List of Atoms
    elif hasattr(entity, "__iter__") and [x for x in entity if x.level == "A"]:
        atom_list = entity
    else:  # Some other weirdo object
        raise ValueError(
            "Center of Mass can only be calculated from the following objects:\n"
            "Structure, Model, Chain, Residue, list of Atoms."
        )

    masses = []
    positions = [[], [], []]  # [ [X1, X2, ..] , [Y1, Y2, ...] , [Z1, Z2, ...] ]

    for atom in atom_list:
        masses.append(atom.mass)

        for i, coord in enumerate(atom.coord.tolist()):
            positions[i].append(coord)

    # If there is a single atom with undefined mass complain loudly.
    if "ukn" in set(masses) and not geometric:
        raise ValueError(
            "Some Atoms don't have an element assigned.\n"
            "Try adding them manually or calculate the geometrical center of mass instead"
        )

    if geometric:
        return [sum(coord_list) / len(masses) for coord_list in positions]
    else:
        w_pos = [[], [], []]
        for atom_index, atom_mass in enumerate(masses):
            w_pos[0].append(positions[0][atom_index] * atom_mass)
            w_pos[1].append(positions[1][atom_index] * atom_mass)
            w_pos[2].append(positions[2][atom_index] * atom_mass)

        return [sum(coord_list) / sum(masses) for coord_list in w_pos]


def fetch_atoms(model, selection="A", atom_bounds=[1, 179]):
    if not isinstance(atom_bounds, (list, tuple)) and len(atom_bounds) > 0:
        raise ValueError("expected non-empty list or tuple, got {}".format(atom_bounds))
    # making sure its a list of lists
    if not isinstance(atom_bounds[0], (list, tuple)):
        atom_bounds = [atom_bounds]
    if not all([len(b) == 2 for b in atom_bounds]):
        raise ValueError(
            "All bounds must be providing one upper "
            "and one lower bound, got {}".format(atom_bounds)
        )
    if not isinstance(selection, (tuple, list)):
        selection = [selection]
    result = []
    for sel in selection:
        for ref_res in model["%s" % sel]:
            resid = ref_res.get_id()[1]
            in_bounds = False
            for bounds in atom_bounds:
                in_bounds |= bounds[0] <= resid and resid <= bounds[1]
            if in_bounds:
                result.append(ref_res["CA"])
    return result


def apply_transformation_to_atoms(model, rotmat, transvec):
    for chain in model:
        for res in chain:
            for atom in res:
                atom.transform(rotmat, transvec)


"""
Function to check inputs
"""


def is_chain_in_pdb(pdbid, input_chain_id):
    from Bio.PDB import PDBParser
    import sys

    pdb_chain_ids_list = []
    structure = PDBParser().get_structure("%s" % pdbid, "%s.pdb" % pdbid)
    model = structure[0]
    for chain in model:
        pdb_chain_ids_list.append(str(chain.get_id()))
    return input_chain_id in pdb_chain_ids_list
    # if input_chain_id not in pdb_chain_ids_list:
    #


def number_of_chains(pdbid):
    from Bio.PDB import PDBParser
    import sys

    pdb_chain_ids_list = []
    structure = PDBParser().get_structure("%s" % pdbid, "%s.pdb" % pdbid)
    model = structure[0]
    counter = 0
    for chain in model:
        counter += 1
    return counter

def str2bool(v):
    if isinstance(v, bool):
       return v
    if v is None:
        return True   
    if v.lower() in ('TRUE', 'True','yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('FALSE','False', 'no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')

"""
Geometrical parameters of TCR-MHC class I
"""


def tcr_mhci_geometrical_parameters(
    pdbid, mhc_a="A", tcr_a="D", tcr_b="E", persist_structure=True
):
    ###############################################################################
    # Define residue range for center of mass and principal component calculations#
    ###############################################################################
    mhc_a_init = 1
    mhc_a_final = 179
    tcr_a_init = 1
    tcr_a_final = 109
    tcr_b_init = 1
    tcr_b_final = 116
    mhc_a_bounds = [1, 179]
    tcr_a_bounds = [1, 109]
    tcr_b_bounds = [1, 116]
    mhci_com_atoms = mhc_a_bounds
    mhci_pca_atoms = [[50, 86], [139, 179]]

    ###################################################################################
    # Import structure and calculate center of mass of CA atoms in MHCI binding groove#
    ###################################################################################
    pdb_parser = Bio.PDB.PDBParser(QUIET=True)
    pdb_io = Bio.PDB.PDBIO()
    sample_structure = pdb_parser.get_structure("sample", "./%s.pdb" % pdbid)
    sample_model = sample_structure[0]

    sample_atoms = fetch_atoms(sample_model, selection=mhc_a, atom_bounds=mhc_a_bounds)
    mhci_com_1 = center_of_mass(sample_atoms, geometric=True)

    ##############################################################################################
    # Extract the xyz coordinates of CA atoms in alpha helices and rotate to princible components#
    ##############################################################################################
    CA_coordinates = [
        x.get_coord() for x in fetch_atoms(sample_model, mhc_a, mhci_pca_atoms)
    ]
    pca_eigvec = pca(CA_coordinates)[2]
    rotation_matrix = pca_eigvec
    apply_transformation_to_atoms(sample_model, rotation_matrix, np.zeros((3,)))

    counterclockwise_z90_matrix = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]])
    apply_transformation_to_atoms(
        sample_model, counterclockwise_z90_matrix, np.zeros(shape=(3,))
    )

    sample_atoms = fetch_atoms(sample_model, mhc_a, mhci_com_atoms)
    mhci_com_2 = center_of_mass(sample_atoms, geometric=True)

    ##########################
    # Translate to the origin#
    ##########################
    translation_vector = np.array(mhci_com_2)
    apply_transformation_to_atoms(sample_model, np.eye(3), -translation_vector)
    sample_atoms = fetch_atoms(sample_model, mhc_a, mhci_com_atoms)

    # Calculate CoM of MHCI binding groove
    mhci_com_3 = center_of_mass(sample_atoms, geometric=True)
    # Calculate CoM of vTCR
    tcr_atoms_for_com = fetch_atoms(sample_model, tcr_a, tcr_a_bounds)
    tcr_atoms_for_com += fetch_atoms(sample_model, tcr_b, tcr_b_bounds)
    vtcr_com = center_of_mass(tcr_atoms_for_com, geometric=True)

    #######################
    # Save final structure#
    #######################
    if persist_structure:
        ali_structure = add_com_to_pdb(mhci_com_3, vtcr_com, sample_model)
        io = Bio.PDB.PDBIO()
        io.set_structure(ali_structure)
        io.save("./%s_rotated.pdb" % pdbid)

    ###################################
    # Calculate geometrical parameters#
    ###################################
    dx, dy, dz = np.subtract(vtcr_com, mhci_com_3)
    r = np.sqrt(np.sum(np.square(np.subtract(vtcr_com, mhci_com_3))))
    theta = np.degrees(np.arctan2(dy, dx))
    phi = np.degrees(np.arccos(dz / r))
    print(
        "The Geomitrical parameters: r = {:.2f}, "
        "theta = {:.2f}, phi = {:.2f}".format(r, theta, phi)
    )
    return r, theta, phi


# tcr_mhci_pos('1ao7', mhc_a='A', tcr_a='D', tcr_b='E')

# ------------
"""
Geometrical parameters of TCR-MHC class II
"""


def tcr_mhcii_geometrical_parameters(
    pdbid, mhc_a="A", mhc_b="B", tcr_a="D", tcr_b="E", persist=True
):
    ###############################################################################
    # Define residue range for center of mass and principal component calculations#
    ###############################################################################
    mhc_a_bounds = [1, 80]
    mhc_b_bounds = [1, 90]
    tcr_a_bounds = [1, 109]
    tcr_b_bounds = [1, 116]
    mhc_a_pca_bounds = [45, 76]
    mhc_b_pca_bounds = [50, 91]

    ###################################################################################
    # Import structure and calculate center of mass of CA atoms in MHCII binding groove#
    ###################################################################################
    pdb_parser = Bio.PDB.PDBParser(QUIET=True)
    pdb_io = Bio.PDB.PDBIO()
    sample_structure = pdb_parser.get_structure("sample", "./%s.pdb" % pdbid)
    sample_model = sample_structure[0]

    sample_atoms = fetch_atoms(sample_model, selection=mhc_a, atom_bounds=mhc_a_bounds)
    mhci_com_1 = center_of_mass(sample_atoms, geometric=True)

    sample_atoms = fetch_atoms(sample_model, mhc_a, mhc_a_bounds)
    sample_atoms += fetch_atoms(sample_model, mhc_b, mhc_b_bounds)
    mhcii_com_1 = center_of_mass(sample_atoms, geometric=True)

    ##############################################################################################
    # Extract the xyz coordinates of CA atoms in alpha helices and rotate to princible components#
    ##############################################################################################
    pca_atoms = fetch_atoms(sample_model, mhc_a, mhc_a_pca_bounds)
    pca_atoms += fetch_atoms(sample_model, mhc_b, mhc_b_pca_bounds)
    CA_coordinates = [x.get_coord() for x in pca_atoms]
    pca_eigvec = pca(CA_coordinates)[2]
    rotation_matrix = pca_eigvec
    apply_transformation_to_atoms(sample_model, rotation_matrix, np.zeros((3,)))

    counterclockwise_z90_matrix = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]])
    apply_transformation_to_atoms(
        sample_model, counterclockwise_z90_matrix, np.zeros((3,))
    )

    sample_atoms = fetch_atoms(sample_model, mhc_a, mhc_a_bounds)
    sample_atoms += fetch_atoms(sample_model, mhc_b, mhc_b_bounds)
    mhcii_com_2 = center_of_mass(sample_atoms, geometric=True)

    #########################
    # Translate to the origin#
    #########################
    translation_vector = np.array(mhcii_com_2)
    apply_transformation_to_atoms(sample_model, np.eye(3), -translation_vector)
    sample_atoms = fetch_atoms(sample_model, mhc_a, mhc_a_bounds)
    sample_atoms += fetch_atoms(sample_model, mhc_b, mhc_b_bounds)

    # Calculate CoM of MHCI binding groove
    mhcii_com_3 = center_of_mass(sample_atoms, geometric=True)
    # Calculate CoM of vTCR
    tcr_atoms_for_com = fetch_atoms(sample_model, tcr_a, tcr_a_bounds)
    tcr_atoms_for_com += fetch_atoms(sample_model, tcr_b, tcr_b_bounds)
    vtcr_com = center_of_mass(tcr_atoms_for_com, geometric=True)

    #######################
    # Save final structure#
    #######################
    if persist:
        ali_structure = add_com_to_pdb(mhcii_com_3, vtcr_com, sample_model)
        io = Bio.PDB.PDBIO()
        io.set_structure(ali_structure)
        io.save("./%s_rotated.pdb" % pdbid)
    #########################
    # Geometrical parameters#
    #########################
    dx, dy, dz = np.subtract(vtcr_com, mhcii_com_3)
    r = np.sqrt(np.sum(np.square(np.subtract(vtcr_com, mhcii_com_3))))
    theta = np.degrees(np.arctan2(dy, dx))
    phi = np.degrees(np.arccos(dz / r))
    print(
        "The Geomitrical parameters: r = {:.2f}, "
        "theta = {:.2f}, phi = {:.2f}".format(r, theta, phi)
    )
    return r, theta, phi


# tcr_mhcii_pos('1FYT', mhc_a='A', mhc_b='B', tcr_a='D', tcr_b='E')

# ------------

# For Python script
args = parser.parse_args()
pdbid = args.pdbid
mhc_a = args.mhc_a
mhc_b = args.mhc_b
tcr_a = args.tcr_a
tcr_b = args.tcr_b
output_pdb = args.output_pdb

input_chain_IDs = list(filter(None, [mhc_a, mhc_b, tcr_a, tcr_b]))
for input_chain_id in input_chain_IDs:
    if not is_chain_in_pdb(pdbid, input_chain_id):
        raise ValueError(
            'Chain "%s" is not found in "%s.pdb"!' % (input_chain_id, pdbid)
        )
n_chains = number_of_chains(pdbid)
if n_chains < 3 or n_chains > 5:
    raise ValueError(
        '"%s.pdb" contains unexpected number of chains! (expected 4, got %s)'
        % (pdbid, n_chains)
    )
if mhc_b is None:
    tcr_mhci_geometrical_parameters(pdbid, mhc_a, tcr_a, tcr_b, str2bool(output_pdb))
else:
    tcr_mhcii_geometrical_parameters(pdbid, mhc_a, mhc_b, tcr_a, tcr_b, str2bool(output_pdb))
