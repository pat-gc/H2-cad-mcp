"""CPU orthographic preview of actual OpenCascade tessellation, in millimetres."""
from pathlib import Path


def render_local_solids(built, path: Path, title: str):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    from matplotlib.ticker import MaxNLocator
    from matplotlib.patches import Patch
    import numpy as np
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopAbs import TopAbs_REVERSED
    from fsgen.fslite.runner import G

    triangles=[]; body_indices=[]
    for body_index, body in enumerate(built.run.solids):
        start=len(triangles)
        BRepMesh_IncrementalMesh(body.shape, 0.0002, False, 0.3, True)
        for face in G.subshapes(body.shape, G.TopAbs_FACE):
            loc=TopLoc_Location()
            mesh=G.BRep_Tool.Triangulation_s(G.TopoDS.Face(face), loc)
            if mesh is None or mesh.NbTriangles() == 0:
                raise ValueError("Local geometry renderer could not tessellate every face")
            points=[mesh.Node(i).Transformed(loc.Transformation()) for i in range(1,mesh.NbNodes()+1)]
            points=np.array([[p.X(),p.Y(),p.Z()] for p in points])*1000
            reverse=G.TopoDS.Face(face).Orientation()==TopAbs_REVERSED
            for i in range(1,mesh.NbTriangles()+1):
                a,b,c=mesh.Triangle(i).Get()
                triangles.append(points[[a-1,c-1,b-1] if reverse else [a-1,b-1,c-1]])
                body_indices.append(body_index)
        if len(triangles)==start:
            raise ValueError('Local geometry renderer could not tessellate every solid')
    triangles=np.asarray(triangles)
    if not len(triangles) or not np.isfinite(triangles).all():
        raise ValueError('Local geometry renderer requires finite solid tessellation')
    palette=np.asarray(plt.get_cmap('tab10').colors)
    base=palette[np.asarray(body_indices)%len(palette)]
    normals=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
    normals/=np.linalg.norm(normals,axis=1,keepdims=True)+1e-12
    # Each panel is a real 2D orthographic projection. Hidden depth axes never
    # contribute ticks or enlarge the projected framing (especially tube ends).
    views=[('Isometric',np.array([1.,1.,0.]),np.array([-1.,1.,1.4]),'',''),
           ('Front (-Y)',np.array([1.,0.,0.]),np.array([0.,0.,1.]),'X (mm)','Z (mm)'),
           ('Top (+Z)',np.array([1.,0.,0.]),np.array([0.,1.,0.]),'X (mm)','Y (mm)'),
           ('Right (+X)',np.array([0.,1.,0.]),np.array([0.,0.,1.]),'Y (mm)','Z (mm)')]
    fig,axes=plt.subplots(2,2,figsize=(12,9))
    fig.subplots_adjust(left=.08,right=.96,bottom=.13,top=.90,wspace=.28,hspace=.35)
    try:
        fig.suptitle(title,fontsize=13,fontweight='bold')
        for ax,(name,horizontal,vertical,xlabel,ylabel) in zip(axes.flat,views):
            horizontal/=np.linalg.norm(horizontal);vertical/=np.linalg.norm(vertical)
            depth=np.cross(horizontal,vertical)
            projected=np.stack((triangles@horizontal,triangles@vertical),axis=-1)
            order=np.argsort((triangles@depth).mean(axis=1),kind='stable')
            light=depth+vertical*.5-horizontal*.25;light/=np.linalg.norm(light)
            shade=.55+.45*np.clip(normals@light,0,1)
            colors=base*shade[:,None]
            ax.add_collection(PolyCollection(projected[order],facecolors=colors[order],
                edgecolors='none',antialiased=False))
            points=projected.reshape(-1,2);lo=points.min(axis=0);hi=points.max(axis=0)
            extent=hi-lo;pad=np.maximum(extent*.08,max(extent.max(),1e-6)*.025)
            ax.set_xlim(lo[0]-pad[0],hi[0]+pad[0]);ax.set_ylim(lo[1]-pad[1],hi[1]+pad[1])
            ax.set_aspect('equal',adjustable='box')
            ax.set_title(name,fontsize=11,loc='left')
            if xlabel:
                ax.set_xlabel(xlabel);ax.set_ylabel(ylabel)
                ax.xaxis.set_major_locator(MaxNLocator(nbins=3));ax.yaxis.set_major_locator(MaxNLocator(nbins=4))
                if extent[0] < extent[1]*.25:
                    ax.set_xticks([(lo[0]+hi[0])/2])
                    ax.set_xlabel(f'{xlabel} · width {extent[0]:g} mm',fontsize=9)
                ax.tick_params(labelsize=9)
                ax.spines[['top','right']].set_visible(False)
            else:
                ax.set_axis_off()
                ax.text(0,.01,'True proportions - millimetres',transform=ax.transAxes,fontsize=9)
        count=len(built.run.solids)
        handles=[Patch(facecolor=palette[i%len(palette)],label=f'Part {i+1}') for i in range(min(count,10))]
        fig.legend(handles=handles,loc='lower center',bbox_to_anchor=(.5,.005),ncols=min(count,5),frameon=False,
                   title=f'{count} actual local solid'+('s' if count!=1 else '')+(f' - first 10 colours shown' if count>10 else ''))
        fig.savefig(path,dpi=140,facecolor='white')
    finally:
        plt.close(fig)
    return path
