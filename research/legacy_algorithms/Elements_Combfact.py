import numpy as np
import os
import glob
import pandas as pd
import matplotlib.pyplot as plt 
import re
kB=8.617330350e-5 #eV/K


def _split_pure_elements(cell_value):
    if pd.isna(cell_value):
        return []
    text = str(cell_value).strip().upper()
    if not text:
        return []
    return [t for t in re.split(r"[,\s;/|+]+", text) if t]


def _has_non_matrix_pure_elements(cell_value, main_elements_normalized):
    tokens = _split_pure_elements(cell_value)
    if not tokens:
        return False
    return any(token not in main_elements_normalized for token in tokens)


def _has_matrix_pure_elements(cell_value, main_elements_normalized):
    tokens = _split_pure_elements(cell_value)
    if not tokens:
        return False
    return any(token in main_elements_normalized for token in tokens)

def U_Calculate(g,A,E,T):
    U=np.zeros(len(g))
    for i in range(len(g)):
        U[i]=g[i]*np.exp(-E[i]/(kB*T))
    return U,np.sum(U)


def rel_intensity(wl,A,E,g,T):
    U_T,U_T_sum=U_Calculate(g,A,E,T)
    rel_intensity=np.zeros(len(wl))
    for i in range(len(wl)):
        rel_intensity[i]=(A[i]*g[i]*np.exp(-E[i]/(kB*T)))/(U_T_sum*wl[i])  
    return rel_intensity

def elements_database(folder_path,T):
    file_list = glob.glob(os.path.join(folder_path, "*.csv"))
    elements_list = [os.path.splitext(os.path.basename(f))[0] for f in file_list]

    elements={}
    for element_name in elements_list: 
        file_path = os.path.join(folder_path, element_name + ".csv")  #
        df = pd.read_csv(file_path,header=1,encoding="gbk")  # 
        df=df.to_numpy()
        even_rows = df[1::2]
        wl=even_rows[:,1]*0.1
        A=even_rows[:,2]
        E=even_rows[:,3]*1.2398*10**(-4) #eV
        g=even_rows[:,7]
       
        wl = wl.astype(float)
        A  = A.astype(float)
        E  = E.astype(float)
        g  = g.astype(float)
     
        mask = (wl >= 200) & (wl <= 900)
        wl = wl[mask]
        A = A[mask]
        E = E[mask]
        g = g[mask]
        
        relative_intensity=rel_intensity(wl,A,E,g,T)
        matrix = np.column_stack((wl, relative_intensity,A,E,g))
        elements[element_name] = { "data": matrix}
    return elements,elements_list

def elements_database_pt2(folder_path, T):
    file_list = glob.glob(os.path.join(folder_path, "*.csv"))
    elements_list = [os.path.splitext(os.path.basename(f))[0] for f in file_list]

    elements = {}
    for element_name in elements_list: 
        file_path = os.path.join(folder_path, element_name + ".csv")


        df = pd.read_csv(file_path, header=1, encoding="gbk")


        df = df.iloc[1::2].copy()


        wl = df.iloc[:, 1]
        A  = df.iloc[:, 2]
        E  = df.iloc[:, 3]
        g  = df.iloc[:, 7]
        if df.shape[1] > 8:
            enable_flag = df.iloc[:, 8]
            enable_mask = enable_flag.isna() | (
                enable_flag.astype(str).str.strip().str.upper().isin(["", "Y"])
            )
         
  
        else:
            enable_mask = pd.Series(True, index=df.index) #problem
            


        wl = pd.to_numeric(wl, errors="coerce")
        A  = pd.to_numeric(A,  errors="coerce")
        E  = pd.to_numeric(E,  errors="coerce")
        g  = pd.to_numeric(g,  errors="coerce")


        wl = wl * 0.1                # 
        E  = E  * 1.2398e-4          #


        valid_mask = (
            enable_mask &
            np.isfinite(wl) &
            np.isfinite(A) & (A > 0) &
            np.isfinite(E) &
            np.isfinite(g)
        )

        wl = wl[valid_mask]
        A  = A[valid_mask]
        E  = E[valid_mask]
        g  = g[valid_mask]

        band_mask = (wl >= 200) & (wl <= 900)

        wl = wl[band_mask]
        A  = A[band_mask]
        E  = E[band_mask]
        g  = g[band_mask]


        wl = wl.to_numpy(dtype=float)
        A  = A.to_numpy(dtype=float)
        E  = E.to_numpy(dtype=float)
        g  = g.to_numpy(dtype=float)

        relative_intensity = rel_intensity(wl, A, E, g, T)

        matrix = np.column_stack((wl, relative_intensity, A, E, g))
        elements[element_name] = {"data": matrix}

    return elements, elements_list

def elements_database_lineswitch(
    folder_path,
    T,
    main_elements,
    LineSwitchMode=False,
    IncludeMatrixPureLinesMode=False,
):
    file_list = glob.glob(os.path.join(folder_path, "*.csv"))
    elements_list = [os.path.splitext(os.path.basename(f))[0] for f in file_list]
    elements = {}
    for element_name in elements_list: 
        # print(f"Processing element: {element_name}")
        file_path = os.path.join(folder_path, element_name + ".csv")

   
        df = pd.read_csv(file_path, header=0, encoding="gbk")

        df = df.iloc[1::2].copy()
        wl = df.iloc[:, 1]
        A  = df.iloc[:, 2]
        E  = df.iloc[:, 3]
        g  = df.iloc[:, 7]
        
        if df.shape[1] > 9:
            enable_flag = df.iloc[:, 8]
            pure_element_flag = df.iloc[:, 9]
            main_elements_normalized = {str(m).strip().upper() for m in main_elements} 
            normalized_pure_element = pure_element_flag.astype(str).str.strip().str.upper()
            base_mask = (
                enable_flag.isna()
                | enable_flag.astype(str).str.strip().str.upper().isin(["", "Y"])
            )


            has_pure_flag = pure_element_flag.notna() & normalized_pure_element.ne("")
            has_matrix_pure = pure_element_flag.apply(
                lambda x: _has_matrix_pure_elements(x, main_elements_normalized)
            )
            non_matrix_pure = pure_element_flag.apply(
                lambda x: _has_non_matrix_pure_elements(x, main_elements_normalized)
            )

            if IncludeMatrixPureLinesMode:
                enable_mask = base_mask | has_matrix_pure
            elif LineSwitchMode:
                enable_mask = (base_mask | (has_pure_flag & non_matrix_pure)) & (~has_matrix_pure)
            else:
                enable_mask = base_mask
        elif df.shape[1] == 9:
            enable_flag = df.iloc[:, 8]
            enable_mask=enable_flag.isna() | enable_flag.astype(str).str.strip().str.upper().isin(["", "Y"])

        else: #此处注意！！！很可能错 也可用于debug
            enable_mask = pd.Series(True, index=df.index)
            # print("Warning: No enable flag column found in {}, all lines will be considered enabled.".format(element_name))


        wl = pd.to_numeric(wl, errors="coerce")
        A  = pd.to_numeric(A,  errors="coerce")
        E  = pd.to_numeric(E,  errors="coerce")
        g  = pd.to_numeric(g,  errors="coerce")


        wl = wl * 0.1              
        E  = E  * 1.2398e-4         
        valid_mask = (
            enable_mask &
            np.isfinite(wl) &
            np.isfinite(A) & (A > 0) &
            np.isfinite(E) &
            np.isfinite(g)
        )

        wl = wl[valid_mask]
        A  = A[valid_mask]
        E  = E[valid_mask]
        g  = g[valid_mask]


        band_mask = (wl >= 200) & (wl <= 900)

        wl = wl[band_mask]
        A  = A[band_mask]
        E  = E[band_mask]
        g  = g[band_mask]

        wl = wl.to_numpy(dtype=float)
        A  = A.to_numpy(dtype=float)
        E  = E.to_numpy(dtype=float)
        g  = g.to_numpy(dtype=float)


        relative_intensity = rel_intensity(wl, A, E, g, T)

        matrix = np.column_stack((wl, relative_intensity, A, E, g))
        elements[element_name] = {"data": matrix}

    return elements, elements_list



