# -*- coding: utf-8 -*-
import sys,numpy as np,os,tempfile; sys.path.insert(0,'.')
from fileio.vtk_writer import write_vti, write_vtu
from fileio.vtk_xml import read_file


def test_all():
    a = np.random.default_rng(1).uniform(0,1,(32,32)).astype(np.float32)
    b = np.random.default_rng(2).uniform(0,1,(32,32)).astype(np.float32)
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d,'test.vti')
        write_vti(p, {'a':a,'b':b}, (32,32))
        r = read_file(p)
        assert r['type']=='ImageData' and r['dimensions']==(32,32,1)
        # reader 返回 flat(不自动 reshape),writer 输入可以 2D 也会被 ravel
        assert np.allclose(r['point_data']['a'], a.ravel(), atol=1e-5)
        assert np.allclose(r['point_data']['b'], b.ravel(), atol=1e-5)
        print('[PASS] vti writer round-trip (flat compare)')
    pts = np.random.default_rng(3).uniform(0,1,(12,3)).astype(np.float32)
    faces = np.array([[0,1,4],[0,4,3],[1,2,5],[1,5,4],[3,4,7],[3,7,6],[4,5,8],[4,8,7]],np.int32)
    cd = np.random.default_rng(4).uniform(0,1,8).astype(np.float32)
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d,'test.vtu')
        write_vtu(p, pts, faces, {'a':cd})
        r = read_file(p)
        assert r['n_points']==12 and r['n_cells']==8
        assert np.allclose(r['points'], pts, atol=1e-5)
        assert np.allclose(r['cell_data']['a'], cd, atol=1e-5)
        print('[PASS] vtu writer round-trip')



if __name__ == "__main__":
    test_all()
    print("all passed")
